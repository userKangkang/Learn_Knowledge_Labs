from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
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
        # Kimi K3: do NOT pass temperature — thinking mode is fixed at 1.0;
        # other values return invalid_request_error.
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "stream": True,
        }
        if model == "kimi-k3":
            body["reasoning_effort"] = self.settings.llm_reasoning_effort
        yield from self._iter_chat_sse(
            url,
            body,
            headers={
                "Authorization": f"Bearer {self.settings.moonshot_api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )

    def extract_kimi_file(self, *, path: str, filename: str, content_type: str) -> str:
        """Upload a document to Kimi's file-extract API and return extracted text.

        The remote file is deleted immediately after extraction. The returned text is
        then supplied to the chat request explicitly because file ids are not chat
        context references in Moonshot's API.
        """
        self.require_provider("kimi")
        base_url = self.settings.moonshot_base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {self.settings.moonshot_api_key}"}
        file_id: str | None = None
        try:
            with httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
                with Path(path).open("rb") as handle:
                    response = client.post(
                        f"{base_url}/files",
                        headers=headers,
                        data={"purpose": "file-extract"},
                        files={"file": (filename, handle, content_type)},
                    )
                if response.status_code >= 400:
                    raise AppError(
                        "KIMI_FILE_UPLOAD_FAILED",
                        f"Kimi 文件上传失败（HTTP {response.status_code}）：{response.text[:500]}",
                        status_code=502,
                    )
                payload = response.json()
                file_id = str(payload.get("id") or "")
                if not file_id:
                    raise AppError("KIMI_FILE_UPLOAD_FAILED", "Kimi 没有返回文件 id", status_code=502)
                extracted = client.get(f"{base_url}/files/{file_id}/content", headers=headers)
                if extracted.status_code >= 400:
                    raise AppError(
                        "KIMI_FILE_EXTRACT_FAILED",
                        f"Kimi 文件解析失败（HTTP {extracted.status_code}）：{extracted.text[:500]}",
                        status_code=502,
                    )
                try:
                    content_payload = extracted.json()
                except ValueError:
                    return extracted.text
                return str(
                    content_payload.get("content")
                    or content_payload.get("text")
                    or content_payload.get("file_content")
                    or ""
                )
        except AppError:
            raise
        except (OSError, httpx.HTTPError, ValueError) as error:
            raise AppError("KIMI_FILE_EXTRACT_FAILED", f"无法解析论文文件：{error}", status_code=502) from error
        finally:
            if file_id:
                try:
                    with httpx.Client(timeout=30.0) as client:
                        client.delete(f"{base_url}/files/{file_id}", headers=headers)
                except httpx.HTTPError:
                    pass

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

    def _iter_chat_sse(
        self,
        url: str,
        body: dict[str, Any],
        *,
        headers: dict[str, str],
        retry_attempt: int = 0,
    ) -> Iterator[StreamChunk]:
        """Read a chat stream, retrying one pre-output transport disconnect.

        A TLS EOF before the first SSE event is safe to replay: nothing has been
        shown or persisted yet.  Once any event has been yielded, retrying would
        risk showing a duplicated answer, so the original error is surfaced.
        """
        yielded_any_chunk = False
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
                            yielded_any_chunk = True
                            yield chunk
        except AppError:
            raise
        except httpx.TimeoutException as error:
            if not yielded_any_chunk and retry_attempt == 0:
                time.sleep(0.5)
                yield from self._iter_chat_sse(url, body, headers=headers, retry_attempt=1)
                return
            raise AppError("LLM_TIMEOUT", "模型请求超时", status_code=504) from error
        except httpx.HTTPError as error:
            if not yielded_any_chunk and retry_attempt == 0:
                time.sleep(0.5)
                yield from self._iter_chat_sse(url, body, headers=headers, retry_attempt=1)
                return
            raise AppError("LLM_UNAVAILABLE", f"无法连接模型服务：{error}", status_code=503) from error

    def _iter_responses_sse(
        self,
        url: str,
        body: dict[str, Any],
        *,
        headers: dict[str, str],
        retry_attempt: int = 0,
    ) -> Iterator[StreamChunk]:
        """Apply the same safe retry policy to Responses API streams."""
        yielded_any_chunk = False
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
                                yielded_any_chunk = True
                                yield StreamChunk(content_delta=delta)
                        elif etype in {
                            "response.web_search_call.in_progress",
                            "response.web_search_call.searching",
                        }:
                            yielded_any_chunk = True
                            yield StreamChunk(status_text="正在联网搜索…")
                        elif etype == "response.web_search_call.completed":
                            yielded_any_chunk = True
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
            if not yielded_any_chunk and retry_attempt == 0:
                time.sleep(0.5)
                yield from self._iter_responses_sse(url, body, headers=headers, retry_attempt=1)
                return
            raise AppError("LLM_TIMEOUT", "DeepSeek 请求超时", status_code=504) from error
        except httpx.HTTPError as error:
            if not yielded_any_chunk and retry_attempt == 0:
                time.sleep(0.5)
                yield from self._iter_responses_sse(url, body, headers=headers, retry_attempt=1)
                return
            raise AppError("LLM_UNAVAILABLE", f"无法连接 DeepSeek：{error}", status_code=503) from error
