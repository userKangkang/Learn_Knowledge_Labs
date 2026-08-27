from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.config import get_settings
from app.schemas.llm import LLMConnectionTestCreate, LLMConnectionTestRead, LLMSettingsRead, RetryStreamCreate, StreamMessageCreate
from app.services.chat_stream_service import ChatStreamService
from app.services.llm_connection import LLMConnectionService

router = APIRouter(tags=["llm"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.get("/llm/settings", response_model=LLMSettingsRead)
def get_llm_settings() -> LLMSettingsRead:
    settings = get_settings()
    return LLMSettingsRead(
        provider="deepseek+kimi+openai",
        model=settings.deepseek_model,
        search_model=settings.deepseek_search_model,
        kimi_model=settings.kimi_model,
        openai_model=settings.openai_model,
        base_url=settings.deepseek_base_url,
        moonshot_base_url=settings.moonshot_base_url,
        openai_base_url=settings.openai_base_url,
        api_key_configured=bool(settings.deepseek_api_key.strip()),
        kimi_api_key_configured=bool(settings.moonshot_api_key.strip()),
        openai_api_key_configured=bool(settings.openai_api_key.strip()),
        temperature=settings.llm_temperature,
        thinking_enabled=settings.llm_thinking_enabled,
        reasoning_effort=settings.llm_reasoning_effort,
        default_text_provider=settings.default_text_provider,
        supports_pdf_text_extract=True,
        supports_image_vision=True,
        web_search_uses_flash=True,
        multimodal_provider="kimi",
    )


@router.post("/llm/test-connection", response_model=LLMConnectionTestRead)
def test_llm_connection(payload: LLMConnectionTestCreate) -> LLMConnectionTestRead:
    return LLMConnectionService().test(payload)


@router.post("/sessions/{session_id}/messages/stream")
def stream_message(
    session_id: str,
    payload: StreamMessageCreate,
    db: Session = Depends(db_session),
) -> StreamingResponse:
    service = ChatStreamService(db)
    prepared = service.prepare(session_id, payload)
    return StreamingResponse(
        service.stream(prepared),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/sessions/{session_id}/messages/retry/stream")
def retry_stream_message(
    session_id: str,
    payload: RetryStreamCreate,
    db: Session = Depends(db_session),
) -> StreamingResponse:
    """Retry the last user message only; soft-deletes trailing assistant replies after it."""
    service = ChatStreamService(db)
    prepared = service.prepare_retry(session_id, payload)
    return StreamingResponse(
        service.stream(prepared),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/llm-requests/{request_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_llm_request(request_id: str) -> Response:
    ChatStreamService.cancel(request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
