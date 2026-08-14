from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError, NotFoundError
from app.models.branch import ConversationBranch
from app.models.context import ContextSnapshot
from app.models.llm_request import LLMRequest
from app.models.message import ChatMessage, MessageRevision
from app.repositories.attachment_repo import AttachmentRepository
from app.repositories.branch_repo import BranchRepository
from app.repositories.context_repo import ContextRepository
from app.repositories.llm_request_repo import LLMRequestRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.session_repo import SessionRepository
from app.schemas.branch import BranchCreate, BranchRead, BranchStreamCreate, EphemeralStreamCreate, TempTurn
from app.schemas.common import LLMRequestStatus, MessageRole, MessageStatus
from app.schemas.message import MessageRead
from app.services.attachment_service import to_attachment_read
from app.services.chat_stream_service import _resolve_route
from app.services.context_builder import estimate_tokens
from app.services.history_for_llm import build_transcript_messages
from app.services.llm_gateway import LLMGateway
from app.services.llm_stream import LLMStreamPersistence, stream_llm_turn
from app.services.llm_prompts import SYSTEM_PROMPT, TEMP_ASK_SYSTEM_ADDON
from app.services.sse import sse_event


class TempChatService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.sessions = SessionRepository(db)
        self.messages = MessageRepository(db)
        self.branches = BranchRepository(db)
        self.llm_requests = LLMRequestRepository(db)
        self.gateway = LLMGateway()
        self.settings = get_settings()

    def _require_session(self, session_id: str):
        session = self.sessions.get_active(session_id)
        if not session:
            raise NotFoundError("SESSION_NOT_FOUND", f"Session {session_id} not found")
        return session

    def _require_anchor(self, session_id: str, anchor_message_id: str) -> ChatMessage:
        anchor = self.messages.get_visible(anchor_message_id)
        if not anchor or anchor.session_id != session_id:
            raise NotFoundError("ANCHOR_NOT_FOUND", "锚定的助手消息不存在")
        if anchor.branch_id is not None:
            raise AppError("ANCHOR_MUST_BE_MAINLINE", "只能挂在主线助手消息下开临时旁支", status_code=400)
        if anchor.role != MessageRole.ASSISTANT.value:
            raise AppError("ANCHOR_MUST_BE_ASSISTANT", "临时询问只能锚定助手消息", status_code=400)
        mainline = self.messages.list_mainline_upto(session_id, anchor_message_id)
        if not mainline or mainline[-1].id != anchor_message_id:
            raise AppError("ANCHOR_NOT_IN_MAINLINE", "锚定消息不在当前会话主线中", status_code=400)
        return anchor

    def _to_message_reads(self, messages: list[ChatMessage]) -> list[MessageRead]:
        attachments = AttachmentRepository(self.db).list_by_message_ids([m.id for m in messages])
        by_message: dict[str, list] = {m.id: [] for m in messages}
        for attachment in attachments:
            if attachment.message_id in by_message:
                by_message[attachment.message_id].append(to_attachment_read(attachment))
        return [
            MessageRead(
                id=m.id,
                session_id=m.session_id,
                role=MessageRole(m.role),
                content=m.content,
                status=MessageStatus(m.status),
                current_revision=m.current_revision,
                llm_request_id=m.llm_request_id,
                provider=m.provider,
                branch_id=m.branch_id,
                attachments=by_message.get(m.id, []),
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in messages
        ]

    def _to_branch_read(self, branch: ConversationBranch, *, include_messages: bool = True) -> BranchRead:
        msgs = self.messages.list_visible_by_branch(branch.id) if include_messages else []
        return BranchRead(
            id=branch.id,
            session_id=branch.session_id,
            anchor_message_id=branch.anchor_message_id,
            title=branch.title,
            message_count=len(msgs) if include_messages else len(self.messages.list_visible_by_branch(branch.id)),
            created_at=branch.created_at,
            messages=self._to_message_reads(msgs) if include_messages else [],
        )

    def list_branches(self, session_id: str, anchor_message_id: str | None = None) -> list[BranchRead]:
        self._require_session(session_id)
        if anchor_message_id:
            self._require_anchor(session_id, anchor_message_id)
            branches = self.branches.list_active_by_anchor(anchor_message_id)
        else:
            branches = self.branches.list_active_by_session(session_id)
        return [self._to_branch_read(b, include_messages=True) for b in branches]

    def get_branch(self, branch_id: str) -> BranchRead:
        branch = self.branches.get_active(branch_id)
        if not branch:
            raise NotFoundError("BRANCH_NOT_FOUND", f"Branch {branch_id} not found")
        return self._to_branch_read(branch, include_messages=True)

    def create_branch(self, session_id: str, payload: BranchCreate) -> BranchRead:
        session = self._require_session(session_id)
        self._require_anchor(session_id, payload.anchor_message_id)
        if not payload.turns:
            raise AppError("BRANCH_EMPTY", "保存旁支至少需要一轮对话", status_code=400)
        for turn in payload.turns:
            if turn.role not in {"USER", "ASSISTANT"}:
                raise AppError("BRANCH_TURN_INVALID", "旁支轮次角色无效", status_code=400)
            if not (turn.content or "").strip():
                raise AppError("BRANCH_TURN_EMPTY", "旁支轮次内容不能为空", status_code=400)

        title = (payload.title or "").strip() or None
        if not title:
            first_user = next((t.content.strip() for t in payload.turns if t.role == "USER"), "")
            title = (first_user[:40] + "…") if len(first_user) > 40 else (first_user or "临时旁支")

        branch = ConversationBranch(
            id=str(uuid4()),
            session_id=session.id,
            anchor_message_id=payload.anchor_message_id,
            title=title,
        )
        self.branches.add(branch)

        for turn in payload.turns:
            content = turn.content.strip()
            message = ChatMessage(
                id=str(uuid4()),
                session_id=session.id,
                branch_id=branch.id,
                role=turn.role,
                content=content,
                status=MessageStatus.ACTIVE.value,
                current_revision=1,
            )
            self.messages.add(message)
            self.messages.add_revision(
                MessageRevision(
                    id=str(uuid4()),
                    message_id=message.id,
                    revision_number=1,
                    content=content,
                )
            )

        self.db.commit()
        self.db.refresh(branch)
        return self._to_branch_read(branch, include_messages=True)

    def delete_branch(self, branch_id: str) -> None:
        branch = self.branches.get_active(branch_id)
        if not branch:
            raise NotFoundError("BRANCH_NOT_FOUND", f"Branch {branch_id} not found")
        for message in self.messages.list_visible_by_branch(branch.id):
            message.status = MessageStatus.DELETED.value
        self.branches.soft_delete(branch)
        self.db.commit()

    def _build_side_llm_messages(
        self,
        *,
        session_id: str,
        anchor: ChatMessage,
        prior_turns: list[TempTurn],
        new_user_text: str,
        provider: str,
        branch_messages: list[ChatMessage] | None = None,
    ) -> tuple[str, list[dict[str, Any]], int]:
        """Mainline up to anchor + side turns. Branch messages never enter the main thread."""
        mainline = self.messages.list_mainline_upto(session_id, anchor.id)
        transcript = build_transcript_messages(mainline, target_provider=provider)
        if branch_messages:
            transcript.extend(build_transcript_messages(branch_messages, target_provider=provider))
        for turn in prior_turns:
            body = (turn.content or "").strip()
            if body:
                transcript.append({"role": turn.role.lower(), "content": body})
        transcript.append({"role": "user", "content": new_user_text})

        system_prompt = f"{SYSTEM_PROMPT}\n\n{TEMP_ASK_SYSTEM_ADDON}"
        estimated = estimate_tokens(system_prompt) + sum(
            estimate_tokens(str(m.get("content") or "")) for m in transcript
        )
        return system_prompt, transcript, estimated

    def prepare_ephemeral(self, session_id: str, payload: EphemeralStreamCreate) -> dict[str, Any]:
        session = self._require_session(session_id)
        anchor = self._require_anchor(session_id, payload.anchor_message_id)
        content = (payload.content or "").strip()
        if not content:
            raise AppError("MESSAGE_EMPTY", "消息内容不能为空", status_code=400)

        provider, model, web_search = _resolve_route(
            text_model=payload.text_model,
            model=None,
            web_search=bool(payload.web_search),
            settings=self.settings,
            file_mode=False,
        )
        self.gateway.require_provider(provider)

        system_prompt, llm_messages, estimated = self._build_side_llm_messages(
            session_id=session_id,
            anchor=anchor,
            prior_turns=payload.prior_turns,
            new_user_text=content,
            provider=provider,
        )

        request_id = str(uuid4())
        return {
            "ephemeral": True,
            "request_id": request_id,
            "node_id": session.node_id,
            "session_id": session.id,
            "anchor_message_id": anchor.id,
            "user_message_id": None,
            "assistant_message_id": None,
            "context_snapshot_id": None,
            "provider": provider,
            "model": model,
            "web_search": web_search,
            "file_mode": False,
            "estimated_input_tokens": estimated,
            "truncated": False,
            "system_prompt": system_prompt,
            "llm_messages": llm_messages,
        }

    def prepare_branch_stream(self, branch_id: str, payload: BranchStreamCreate) -> dict[str, Any]:
        branch = self.branches.get_active(branch_id)
        if not branch:
            raise NotFoundError("BRANCH_NOT_FOUND", f"Branch {branch_id} not found")
        session = self._require_session(branch.session_id)
        anchor = self._require_anchor(branch.session_id, branch.anchor_message_id)

        content = (payload.content or "").strip()
        if not content:
            raise AppError("MESSAGE_EMPTY", "消息内容不能为空", status_code=400)

        provider, model, web_search = _resolve_route(
            text_model=payload.text_model,
            model=None,
            web_search=bool(payload.web_search),
            settings=self.settings,
            file_mode=False,
        )
        self.gateway.require_provider(provider)

        branch_history = self.messages.list_visible_by_branch(branch.id)
        system_prompt, llm_messages, estimated = self._build_side_llm_messages(
            session_id=branch.session_id,
            anchor=anchor,
            prior_turns=[],
            new_user_text=content,
            provider=provider,
            branch_messages=branch_history,
        )

        user_message = ChatMessage(
            id=str(uuid4()),
            session_id=session.id,
            branch_id=branch.id,
            role=MessageRole.USER.value,
            content=content,
            status=MessageStatus.ACTIVE.value,
            current_revision=1,
            provider=provider,
        )
        self.messages.add(user_message)
        self.messages.add_revision(
            MessageRevision(id=str(uuid4()), message_id=user_message.id, revision_number=1, content=content)
        )

        assistant_message = ChatMessage(
            id=str(uuid4()),
            session_id=session.id,
            branch_id=branch.id,
            role=MessageRole.ASSISTANT.value,
            content="",
            status=MessageStatus.STREAMING.value,
            current_revision=1,
            provider=provider,
        )
        self.messages.add(assistant_message)
        self.messages.add_revision(
            MessageRevision(id=str(uuid4()), message_id=assistant_message.id, revision_number=1, content="")
        )

        snapshot = ContextSnapshot(
            id=str(uuid4()),
            node_id=session.node_id,
            session_id=session.id,
            policy_version=0,
            rendered_system_prompt=system_prompt,
            rendered_context=f"[temp-branch:{branch.id}] {content}",
            estimated_input_tokens=estimated,
            truncated=False,
        )
        ContextRepository(self.db).add_snapshot(snapshot)

        request = LLMRequest(
            id=str(uuid4()),
            node_id=session.node_id,
            session_id=session.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            context_snapshot_id=snapshot.id,
            provider=provider,
            model=model,
            status=LLMRequestStatus.PENDING.value,
            input_tokens=estimated,
        )
        self.llm_requests.add(request)
        assistant_message.llm_request_id = request.id
        user_message.llm_request_id = request.id
        self.db.commit()

        return {
            "ephemeral": False,
            "request_id": request.id,
            "node_id": session.node_id,
            "session_id": session.id,
            "branch_id": branch.id,
            "anchor_message_id": anchor.id,
            "user_message_id": user_message.id,
            "assistant_message_id": assistant_message.id,
            "context_snapshot_id": snapshot.id,
            "provider": provider,
            "model": model,
            "web_search": web_search,
            "file_mode": False,
            "estimated_input_tokens": estimated,
            "truncated": False,
            "system_prompt": system_prompt,
            "llm_messages": llm_messages,
        }

    def stream(self, prepared: dict[str, Any]) -> Iterator[str]:
        ephemeral = bool(prepared.get("ephemeral"))
        persistence = None if ephemeral else LLMStreamPersistence(self.db)
        yield from stream_llm_turn(
            prepared,
            gateway=self.gateway,
            set_streaming=None if persistence is None else lambda: persistence.set_streaming(prepared["request_id"]),
            finalize=None if persistence is None else (
                lambda status, content, input_tokens, output_tokens, error_code, error_message: persistence.finalize(
                    prepared["request_id"],
                    status=status,
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    error_code=error_code,
                    error_message=error_message,
                )
            ),
            extra_created={
                "ephemeral": ephemeral,
                "branch_id": prepared.get("branch_id"),
                "anchor_message_id": prepared.get("anchor_message_id"),
            },
            extra_completed={"ephemeral": ephemeral},
        )
