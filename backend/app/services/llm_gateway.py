from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.errors import AppError


@dataclass
class StreamChunk:
    content_delta: str = ""
    status_text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None


class LLMGateway:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def require_provider(self, provider: str) -> None:
        if provider == "kimi":
            if not (self.settings.moonshot_api_key or "").strip():
                raise AppError(
                    "KIMI_NOT_CONFIGURED",
                    "未配置 Kimi/Moonshot API Key。请在 backend/.env 设置 MOONSHOT_API_KEY 或 KIMI_API_KEY。",
                    status_code=503,
                )
            return
        if not (self.settings.deepseek_api_key or "").strip():
            raise AppError(
                "LLM_NOT_CONFIGURED",
                "未配置 DeepSeek API Key。请在 backend/.env 设置 DEEPSEEK_API_KEY。",
                status_code=503,
            )

    def stream(
        self,
        *,
        provider: str,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        web_search: bool = False,
    ) -> Iterator[StreamChunk]:
        if provider == "kimi":
            yield from self._stream_kimi_chat(model=model, system_prompt=system_prompt, messages=messages)
            return
        if web_search:
            # Responses API expects instructions + single input string.
            user_blob = self._flatten_messages_for_responses(messages)
            yield from self._stream_responses_with_search(
                system_prompt=system_prompt,
                user_content=user_blob,
                model=model,
            )
            return
        yield from self._stream_deepseek_chat(
            model=model,
            system_prompt=system_prompt,
            messages=messages,
        )

    @staticmethod
    def _flatten_messages_for_responses(messages: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content")
            if isinstance(content, list):
                texts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                content = "\n".join(t for t in texts if t)
            parts.append(f"[{role}] {content}")
        return "\n\n".join(parts)

    def _stream_deepseek_chat(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> Iterator[StreamChunk]:
        self.require_provider("deepseek")
        url = f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions"
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "stream": True,
            "stream_options": {"include_usage": True},
            "thinking": {"type": "enabled"},
            "reasoning_effort": self.settings.llm_reasoning_effort,
        }
        yield from self._iter_chat_sse(
            url,
            body,
            headers={
                "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )

    def _stream_kimi_chat(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> Iterator[StreamChunk]:
        self.require_provider("kimi")
        url = f"{self.settings.moonshot_base_url.rstrip('/')}/chat/completions"
        # kimi-k2.6 / k3: do NOT pass temperature — thinking mode is fixed at 1.0;
        # other values return invalid_request_error.
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "stream": True,
        }
        yield from self._iter_chat_sse(
            url,
            body,
            headers={
                "Authorization": f"Bearer {self.settings.moonshot_api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )

    def _stream_responses_with_search(
        self,
        *,
        system_prompt: str,
        user_content: str,
        model: str,
    ) -> Iterator[StreamChunk]:
        self.require_provider("deepseek")
        url = f"{self.settings.deepseek_base_url.rstrip('/')}/responses"
        body: dict[str, Any] = {
            "model": model,
            "instructions": system_prompt,
            "input": user_content,
            "stream": True,
            "tools": [{"type": "web_search"}],
            "tool_choice": "auto",
            "reasoning": {"effort": self.settings.llm_reasoning_effort},
        }
        yield from self._iter_responses_sse(
            url,
            body,
            headers={
                "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )

    def _iter_chat_sse(self, url: str, body: dict[str, Any], *, headers: dict[str, str]) -> Iterator[StreamChunk]:
        try:
            with httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
                with client.stream("POST", url, headers=headers, json=body) as response:
                    if response.status_code >= 400:
                        detail = response.read().decode("utf-8", errors="replace")
                        raise AppError(
                            "LLM_PROVIDER_ERROR",
                            f"模型请求失败（HTTP {response.status_code}）：{detail[:500]}",
                            status_code=502,
                        )
                    for line in response.iter_lines():
                        if not line or line.startswith(":") or not line.startswith("data:"):
                            continue
                        data = line.removeprefix("data:").strip()
                        if data == "[DONE]":
                            return
                        try:
                            payload = json.loads(data)
                        except json.JSONDecodeError as error:
                            raise AppError("LLM_STREAM_INVALID", "流式响应无法解析", status_code=502) from error

                        chunk = StreamChunk()
                        usage = payload.get("usage") or {}
                        if usage:
                            chunk.input_tokens = usage.get("prompt_tokens")
                            chunk.output_tokens = usage.get("completion_tokens")
                        choices = payload.get("choices") or []
                        if choices:
                            delta = choices[0].get("delta") or {}
                            content = delta.get("content")
                            if isinstance(content, str) and content:
                                chunk.content_delta = content
                            chunk.finish_reason = choices[0].get("finish_reason")
                        if chunk.content_delta or chunk.input_tokens is not None or chunk.finish_reason:
                            yield chunk
        except AppError:
            raise
        except httpx.TimeoutException as error:
            raise AppError("LLM_TIMEOUT", "模型请求超时", status_code=504) from error
        except httpx.HTTPError as error:
            raise AppError("LLM_UNAVAILABLE", f"无法连接模型服务：{error}", status_code=503) from error

    def _iter_responses_sse(self, url: str, body: dict[str, Any], *, headers: dict[str, str]) -> Iterator[StreamChunk]:
        try:
            with httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
                with client.stream("POST", url, headers=headers, json=body) as response:
                    if response.status_code >= 400:
                        detail = response.read().decode("utf-8", errors="replace")
                        raise AppError(
                            "LLM_PROVIDER_ERROR",
                            f"DeepSeek Responses 请求失败（HTTP {response.status_code}）：{detail[:500]}",
                            status_code=502,
                        )

                    event_name = "message"
                    for line in response.iter_lines():
                        if not line:
                            event_name = "message"
                            continue
                        if line.startswith(":"):
                            continue
                        if line.startswith("event:"):
                            event_name = line.removeprefix("event:").strip()
                            continue
                        if not line.startswith("data:"):
                            continue
                        raw = line.removeprefix("data:").strip()
                        try:
                            payload = json.loads(raw)
                        except json.JSONDecodeError as error:
                            raise AppError("LLM_STREAM_INVALID", "DeepSeek Responses 流无法解析", status_code=502) from error

                        etype = payload.get("type") or event_name
                        if etype == "response.output_text.delta":
                            delta = payload.get("delta")
                            if isinstance(delta, str) and delta:
                                yield StreamChunk(content_delta=delta)
                        elif etype in {
                            "response.web_search_call.in_progress",
                            "response.web_search_call.searching",
                        }:
                            yield StreamChunk(status_text="正在联网搜索…")
                        elif etype == "response.web_search_call.completed":
                            yield StreamChunk(status_text="搜索完成，正在整理回答…")
                        elif etype in {"response.completed", "response.incomplete"}:
                            resp = payload.get("response") or {}
                            usage = resp.get("usage") or {}
                            yield StreamChunk(
                                input_tokens=usage.get("input_tokens"),
                                output_tokens=usage.get("output_tokens"),
                                finish_reason="stop" if etype == "response.completed" else "length",
                            )
                            return
                        elif etype == "response.failed":
                            resp = payload.get("response") or {}
                            err = resp.get("error") or {}
                            raise AppError(
                                "LLM_PROVIDER_ERROR",
                                str(err.get("message") or "DeepSeek Responses 失败"),
                                status_code=502,
                            )
        except AppError:
            raise
        except httpx.TimeoutException as error:
            raise AppError("LLM_TIMEOUT", "DeepSeek 请求超时", status_code=504) from error
        except httpx.HTTPError as error:
            raise AppError("LLM_UNAVAILABLE", f"无法连接 DeepSeek：{error}", status_code=503) from error
