"""Shared orchestration for streaming an LLM turn over SSE with persistence."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.errors import AppError
from app.models.llm_request import LLMRequest
from app.models.message import ChatMessage, MessageRevision
from app.repositories.message_repo import MessageRepository
from app.schemas.common import LLMRequestStatus, MessageStatus
from app.services import cancel_registry
from app.services.context_builder import estimate_tokens
from app.services.llm_gateway import LLMGateway
from app.services.sse import sse_event

FinalizeFn = Callable[[LLMRequestStatus, str, int | None, int | None, str | None, str | None], None]


class LLMStreamPersistence:
    """Persist LLMRequest / assistant-message state for a streamed turn."""

    def __init__(self, db) -> None:
        self.db = db
        self.messages = MessageRepository(db)

    def set_streaming(self, request_id: str) -> None:
        request = self.db.get(LLMRequest, request_id)
        if request:
            request.status = LLMRequestStatus.STREAMING.value
            self.db.commit()

    def finalize(
        self,
        request_id: str,
        *,
        status: LLMRequestStatus,
        content: str,
        input_tokens: int | None,
        output_tokens: int | None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        request = self.db.get(LLMRequest, request_id)
        if not request:
            return
        request.status = status.value
        request.input_tokens = input_tokens
        request.output_tokens = output_tokens
        request.error_code = error_code
        request.error_message = error_message
        request.completed_at = datetime.now(UTC)

        assistant = self.db.get(ChatMessage, request.assistant_message_id) if request.assistant_message_id else None
        if assistant:
            assistant.content = content
            assistant.provider = request.provider
            if status == LLMRequestStatus.SUCCEEDED:
                assistant.status = MessageStatus.ACTIVE.value
            elif status == LLMRequestStatus.CANCELLED and not content.strip():
                assistant.status = MessageStatus.DELETED.value
            else:
                assistant.status = MessageStatus.FAILED.value
            revisions = self.messages.list_revisions(assistant.id)
            if revisions:
                revisions[0].content = content
            else:
                self.db.add(
                    MessageRevision(
                        id=str(uuid4()),
                        message_id=assistant.id,
                        revision_number=1,
                        content=content,
                    )
                )
        self.db.commit()


def stream_llm_turn(
    prepared: dict[str, Any],
    *,
    gateway: LLMGateway,
    set_streaming: Callable[[], None] | None = None,
    finalize: FinalizeFn | None = None,
    extra_created: dict[str, Any] | None = None,
    extra_completed: dict[str, Any] | None = None,
) -> Iterator[str]:
    """Run one prepared LLM turn, emitting SSE events and optionally persisting.

    Pass ``finalize=None`` (and ``set_streaming=None``) for ephemeral turns that
    have no LLMRequest row to persist.
    """
    request_id = prepared["request_id"]
    cancel_registry.clear_cancel(request_id)

    yield sse_event(
        "request_created",
        {
            "request_id": request_id,
            "user_message_id": prepared.get("user_message_id"),
            "assistant_message_id": prepared.get("assistant_message_id"),
            "provider": prepared["provider"],
            "model": prepared["model"],
            "web_search": prepared["web_search"],
            "file_mode": prepared.get("file_mode", False),
            **(extra_created or {}),
        },
    )
    yield sse_event(
        "context_built",
        {
            "context_snapshot_id": prepared.get("context_snapshot_id"),
            "estimated_input_tokens": prepared["estimated_input_tokens"],
            "truncated": prepared.get("truncated", False),
        },
    )

    if set_streaming is not None:
        set_streaming()

    def persist(
        status: LLMRequestStatus,
        content: str,
        input_tokens: int | None,
        output_tokens: int | None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        if finalize is not None:
            finalize(status, content, input_tokens, output_tokens, error_code, error_message)

    full_text = ""
    input_tokens = prepared["estimated_input_tokens"]
    output_tokens: int | None = None

    try:
        for chunk in gateway.stream(
            provider=prepared["provider"],
            model=prepared["model"],
            system_prompt=prepared["system_prompt"],
            messages=prepared["llm_messages"],
            web_search=prepared["web_search"],
            cancel_check=lambda: cancel_registry.is_cancelled(request_id),
        ):
            if cancel_registry.is_cancelled(request_id):
                persist(LLMRequestStatus.CANCELLED, full_text, input_tokens, output_tokens, error_code="CANCELLED", error_message="用户取消")
                yield sse_event("cancelled", {"request_id": request_id})
                return

            if chunk.input_tokens is not None:
                input_tokens = chunk.input_tokens
            if chunk.output_tokens is not None:
                output_tokens = chunk.output_tokens
            if chunk.status_text:
                yield sse_event("status", {"request_id": request_id, "message": chunk.status_text})
            if chunk.content_delta:
                full_text += chunk.content_delta
                yield sse_event(
                    "delta",
                    {
                        "request_id": request_id,
                        "assistant_message_id": prepared.get("assistant_message_id"),
                        "delta": chunk.content_delta,
                    },
                )

        if cancel_registry.is_cancelled(request_id):
            persist(LLMRequestStatus.CANCELLED, full_text, input_tokens, output_tokens, error_code="CANCELLED", error_message="用户取消")
            yield sse_event("cancelled", {"request_id": request_id})
            return

        if not full_text.strip():
            raise AppError("LLM_EMPTY_RESPONSE", "模型返回空内容", status_code=502)

        if output_tokens is None:
            output_tokens = estimate_tokens(full_text)

        persist(LLMRequestStatus.SUCCEEDED, full_text, input_tokens, output_tokens)
        yield sse_event(
            "completed",
            {
                "request_id": request_id,
                "assistant_message_id": prepared.get("assistant_message_id"),
                "content": full_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                **(extra_completed or {}),
            },
        )
    except AppError as error:
        persist(LLMRequestStatus.FAILED, full_text, input_tokens, output_tokens, error_code=error.code, error_message=error.message)
        yield sse_event(
            "failed",
            {"request_id": request_id, "error_code": error.code, "error_message": error.message},
        )
    except Exception as error:  # noqa: BLE001
        persist(LLMRequestStatus.FAILED, full_text, input_tokens, output_tokens, error_code="LLM_UNEXPECTED_ERROR", error_message=str(error))
        yield sse_event(
            "failed",
            {
                "request_id": request_id,
                "error_code": "LLM_UNEXPECTED_ERROR",
                "error_message": str(error),
            },
        )
    finally:
        cancel_registry.clear_cancel(request_id)
