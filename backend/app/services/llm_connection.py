"""One-shot provider connectivity checks used by the global UI tester."""

from time import perf_counter

from app.config import get_settings
from app.errors import AppError
from app.schemas.llm import LLMConnectionTestCreate, LLMConnectionTestRead
from app.services.llm_gateway import LLMGateway
from app.services.model_routing import resolve_text_route


class LLMConnectionService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.gateway = LLMGateway(self.settings)

    def test(self, payload: LLMConnectionTestCreate) -> LLMConnectionTestRead:
        provider, model, _ = resolve_text_route(
            text_model=payload.text_model,
            web_search=False,
            settings=self.settings,
        )
        started = perf_counter()
        response = ""
        try:
            self.gateway.require_provider(provider)
            for chunk in self.gateway.stream(
                provider=provider,
                model=model,
                system_prompt="你是 AI 连接测试助手。只需简短回复“连接正常”，不要联网，不要调用工具。",
                messages=[{"role": "user", "content": "请回复“连接正常”，用于测试当前模型连接。"}],
                web_search=False,
            ):
                response += chunk.content_delta or ""
        except AppError:
            raise
        except Exception as error:  # noqa: BLE001
            raise AppError("LLM_TEST_UNEXPECTED", f"AI 连接测试异常：{error}", status_code=502) from error

        if not response.strip():
            raise AppError("LLM_EMPTY_RESPONSE", "AI 连接成功但没有返回可读内容", status_code=502)
        return LLMConnectionTestRead(
            provider=provider,
            model=model,
            response=response.strip(),
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
        )
