from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import SessionLocal
from app.errors import AppError, NotFoundError
from app.models.llm_request import LLMRequest
from app.models.message import ChatMessage, MessageRevision
from app.repositories.attachment_repo import AttachmentRepository
from app.repositories.llm_request_repo import LLMRequestRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.session_repo import SessionRepository
from app.schemas.common import LLMRequestStatus, MessageRole, MessageStatus
from app.schemas.llm import RetryStreamCreate, StreamMessageCreate
from app.services import cancel_registry
from app.services.attachment_service import AttachmentService
from app.services.context_builder import ContextBuilder, estimate_tokens
from app.services.history_for_llm import build_file_digest_user_content, build_transcript_messages
from app.services.llm_gateway import LLMGateway
from app.services.llm_prompts import FILE_DIGEST_SYSTEM_ADDON, SYSTEM_PROMPT


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _compose_snapshot_prompt(content: str, attachments) -> str:
    parts = [content.strip()]
    for attachment in attachments:
        kind = getattr(attachment, "kind", None) or "pdf"
        if kind == "image":
            parts.append(f"[图片附件 {attachment.filename}]（本轮由 Kimi 视觉解析）")
        elif attachment.extracted_text:
            parts.append(f"[附件 {attachment.filename}]\n{attachment.extracted_text}")
        else:
            parts.append(f"[附件 {attachment.filename}]（未能提取文本）")
    return "\n\n".join(p for p in parts if p)


def _resolve_route(
    *,
    text_model: str | None,
    model: str | None,
    web_search: bool,
    settings,
    file_mode: bool,
) -> tuple[str, str, bool]:
    """Return provider, model, web_search."""
    if file_mode:
        return "kimi", settings.kimi_model.strip(), False

    if web_search:
        return "deepseek", settings.deepseek_search_model.strip(), True

    choice = (text_model or model or "").strip()
    if not choice:
        choice = settings.kimi_model if settings.default_text_provider == "kimi" else settings.deepseek_model

    if choice.startswith("kimi") or choice == settings.kimi_model:
        return "kimi", settings.kimi_model.strip(), False
    return "deepseek", settings.deepseek_model.strip(), False



class ChatStreamService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.sessions = SessionRepository(db)
        self.messages = MessageRepository(db)
        self.attachments = AttachmentRepository(db)
        self.llm_requests = LLMRequestRepository(db)
        self.attachment_service = AttachmentService(db)
        self.builder = ContextBuilder(db)
        self.gateway = LLMGateway()
        self.settings = get_settings()

    def prepare(self, session_id: str, payload: StreamMessageCreate) -> dict[str, Any]:
        session = self.sessions.get_active(session_id)
        if not session:
            raise NotFoundError("SESSION_NOT_FOUND", f"Session {session_id} not found")

        content = (payload.content or "").strip()
        if not content and not payload.attachment_ids:
            raise AppError("MESSAGE_EMPTY", "消息内容与附件不能同时为空", status_code=400)

        file_mode = bool(payload.attachment_ids)
        provider, model, web_search = _resolve_route(
            text_model=payload.text_model,
            model=payload.model,
            web_search=bool(payload.web_search),
            settings=self.settings,
            file_mode=file_mode,
        )
        self.gateway.require_provider(provider)

        display_content = content or ("请解析附件" if file_mode else "（空）")
        user_message = ChatMessage(
            id=str(uuid4()),
            session_id=session.id,
            role=MessageRole.USER.value,
            content=display_content,
            status=MessageStatus.ACTIVE.value,
            current_revision=1,
            provider=provider,
        )
        self.messages.add(user_message)
        self.messages.add_revision(
            MessageRevision(
                id=str(uuid4()),
                message_id=user_message.id,
                revision_number=1,
                content=display_content,
            )
        )

        attachments = []
        if payload.attachment_ids:
            attachments = self.attachment_service.bind_to_message(
                payload.attachment_ids,
                session_id=session_id,
                message_id=user_message.id,
            )

        return self._prepare_assistant_turn(
            session=session,
            user_message=user_message,
            attachments=attachments,
            user_text=content,
            provider=provider,
            model=model,
            web_search=web_search,
            file_mode=file_mode,
        )

    def prepare_retry(self, session_id: str, payload: RetryStreamCreate) -> dict[str, Any]:
        """Retry only the last visible user message; soft-delete trailing replies after it."""
        session = self.sessions.get_active(session_id)
        if not session:
            raise NotFoundError("SESSION_NOT_FOUND", f"Session {session_id} not found")

        visible = self.messages.list_visible_by_session(session_id)
        last_user_idx = next(
            (i for i in range(len(visible) - 1, -1, -1) if visible[i].role == MessageRole.USER.value),
            None,
        )
        if last_user_idx is None:
            raise AppError("NOTHING_TO_RETRY", "没有可重试的用户消息", status_code=400)

        user_message = visible[last_user_idx]
        for trailing in visible[last_user_idx + 1 :]:
            if trailing.status == MessageStatus.STREAMING.value and trailing.llm_request_id:
                cancel_registry.request_cancel(trailing.llm_request_id)
            trailing.status = MessageStatus.DELETED.value
        self.db.flush()

        attachments = self.attachments.list_by_message_ids([user_message.id])
        file_mode = bool(attachments)
        provider, model, web_search = _resolve_route(
            text_model=payload.text_model,
            model=payload.model,
            web_search=bool(payload.web_search),
            settings=self.settings,
            file_mode=file_mode,
        )
        self.gateway.require_provider(provider)
        user_message.provider = provider

        user_text = (user_message.content or "").strip()
        if user_text in {"请解析附件", "（空）"}:
            user_text = ""

        return self._prepare_assistant_turn(
            session=session,
            user_message=user_message,
            attachments=attachments,
            user_text=user_text,
            provider=provider,
            model=model,
            web_search=web_search,
            file_mode=file_mode,
        )

    def _prepare_assistant_turn(
        self,
        *,
        session,
        user_message: ChatMessage,
        attachments,
        user_text: str,
        provider: str,
        model: str,
        web_search: bool,
        file_mode: bool,
    ) -> dict[str, Any]:
        snapshot_prompt = _compose_snapshot_prompt(user_message.content, attachments)
        build = self.builder.build(
            session.id,
            snapshot_prompt,
            persist=True,
            exclude_message_ids={user_message.id},
            target_provider=provider,
        )
        assert build.snapshot_id

        assistant_message = ChatMessage(
            id=str(uuid4()),
            session_id=session.id,
            role=MessageRole.ASSISTANT.value,
            content="",
            status=MessageStatus.STREAMING.value,
            current_revision=1,
            provider=provider,
        )
        self.messages.add(assistant_message)
        self.messages.add_revision(
            MessageRevision(
                id=str(uuid4()),
                message_id=assistant_message.id,
                revision_number=1,
                content="",
            )
        )

        request = LLMRequest(
            id=str(uuid4()),
            node_id=session.node_id,
            session_id=session.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            context_snapshot_id=build.snapshot_id,
            provider=provider,
            model=model,
            status=LLMRequestStatus.PENDING.value,
            input_tokens=build.estimated_input_tokens,
        )
        self.llm_requests.add(request)
        assistant_message.llm_request_id = request.id
        user_message.llm_request_id = request.id
        self.db.commit()

        if file_mode:
            system_prompt = f"{SYSTEM_PROMPT}\n\n{FILE_DIGEST_SYSTEM_ADDON}"
            history = self.messages.list_visible_by_session(session.id)
            transcript = build_transcript_messages(
                history,
                target_provider=provider,
                exclude_message_ids={user_message.id, assistant_message.id},
            )
            user_content, _ = build_file_digest_user_content(
                user_text=user_text,
                attachments=attachments,
            )
            llm_messages: list[dict[str, Any]] = [*transcript, {"role": "user", "content": user_content}]
        else:
            system_prompt = SYSTEM_PROMPT
            # Keep audit snapshot richness; send as a single user turn of final text only.
            llm_messages = [{"role": "user", "content": build.rendered_context}]

        return {
            "request_id": request.id,
            "node_id": session.node_id,
            "session_id": session.id,
            "user_message_id": user_message.id,
            "assistant_message_id": assistant_message.id,
            "context_snapshot_id": build.snapshot_id,
            "provider": provider,
            "model": model,
            "web_search": web_search,
            "file_mode": file_mode,
            "estimated_input_tokens": build.estimated_input_tokens,
            "truncated": build.truncated,
            "system_prompt": system_prompt,
            "llm_messages": llm_messages,
        }

    def stream(self, prepared: dict[str, Any]) -> Iterator[str]:
        request_id = prepared["request_id"]
        cancel_registry.clear_cancel(request_id)

        yield _sse(
            "request_created",
            {
                "request_id": request_id,
                "user_message_id": prepared["user_message_id"],
                "assistant_message_id": prepared["assistant_message_id"],
                "provider": prepared["provider"],
                "model": prepared["model"],
                "web_search": prepared["web_search"],
                "file_mode": prepared["file_mode"],
            },
        )
        yield _sse(
            "context_built",
            {
                "context_snapshot_id": prepared["context_snapshot_id"],
                "estimated_input_tokens": prepared["estimated_input_tokens"],
                "truncated": prepared["truncated"],
            },
        )

        self._set_status(request_id, LLMRequestStatus.STREAMING)

        full_text = ""
        input_tokens = prepared["estimated_input_tokens"]
        output_tokens: int | None = None

        try:
            for chunk in self.gateway.stream(
                provider=prepared["provider"],
                model=prepared["model"],
                system_prompt=prepared["system_prompt"],
                messages=prepared["llm_messages"],
                web_search=prepared["web_search"],
            ):
                if cancel_registry.is_cancelled(request_id):
                    self._finalize(
                        request_id,
                        status=LLMRequestStatus.CANCELLED,
                        content=full_text,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        error_code="CANCELLED",
                        error_message="用户取消",
                    )
                    yield _sse("cancelled", {"request_id": request_id})
                    return

                if chunk.input_tokens is not None:
                    input_tokens = chunk.input_tokens
                if chunk.output_tokens is not None:
                    output_tokens = chunk.output_tokens
                if chunk.status_text:
                    yield _sse(
                        "status",
                        {
                            "request_id": request_id,
                            "message": chunk.status_text,
                        },
                    )
                if chunk.content_delta:
                    full_text += chunk.content_delta
                    yield _sse(
                        "delta",
                        {
                            "request_id": request_id,
                            "assistant_message_id": prepared["assistant_message_id"],
                            "delta": chunk.content_delta,
                        },
                    )

            if cancel_registry.is_cancelled(request_id):
                self._finalize(
                    request_id,
                    status=LLMRequestStatus.CANCELLED,
                    content=full_text,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    error_code="CANCELLED",
                    error_message="用户取消",
                )
                yield _sse("cancelled", {"request_id": request_id})
                return

            if not full_text.strip():
                raise AppError("LLM_EMPTY_RESPONSE", "模型返回空内容", status_code=502)

            if output_tokens is None:
                output_tokens = estimate_tokens(full_text)

            self._finalize(
                request_id,
                status=LLMRequestStatus.SUCCEEDED,
                content=full_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            yield _sse(
                "completed",
                {
                    "request_id": request_id,
                    "assistant_message_id": prepared["assistant_message_id"],
                    "content": full_text,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )
        except AppError as error:
            self._finalize(
                request_id,
                status=LLMRequestStatus.FAILED,
                content=full_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error_code=error.code,
                error_message=error.message,
            )
            yield _sse(
                "failed",
                {
                    "request_id": request_id,
                    "error_code": error.code,
                    "error_message": error.message,
                },
            )
        except Exception as error:  # noqa: BLE001
            self._finalize(
                request_id,
                status=LLMRequestStatus.FAILED,
                content=full_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error_code="LLM_UNEXPECTED_ERROR",
                error_message=str(error),
            )
            yield _sse(
                "failed",
                {
                    "request_id": request_id,
                    "error_code": "LLM_UNEXPECTED_ERROR",
                    "error_message": str(error),
                },
            )
        finally:
            cancel_registry.clear_cancel(request_id)

    @staticmethod
    def cancel(request_id: str) -> None:
        # Always mark cancel flag (covers ephemeral streams with no LLMRequest row).
        cancel_registry.request_cancel(request_id)
        db = SessionLocal()
        try:
            request = db.get(LLMRequest, request_id)
            if not request:
                return
            if request.status in {
                LLMRequestStatus.SUCCEEDED.value,
                LLMRequestStatus.FAILED.value,
                LLMRequestStatus.CANCELLED.value,
            }:
                return
        finally:
            db.close()

    def _set_status(self, request_id: str, status: LLMRequestStatus) -> None:
        request = self.db.get(LLMRequest, request_id)
        if request:
            request.status = status.value
            self.db.commit()

    def _finalize(
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
