from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import AppError, NotFoundError
from app.models.message import ChatMessage, MessageRevision
from app.models.session import ConversationSession
from app.repositories.attachment_repo import AttachmentRepository
from app.repositories.branch_repo import BranchRepository
from app.repositories.context_repo import ContextRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.node_repo import NodeRepository
from app.repositories.session_repo import SessionRepository
from app.schemas.common import MessageRole, MessageStatus
from app.schemas.message import MessageCreate, MessageRead, MessageUpdate
from app.schemas.session import SessionCreate, SessionUpdate
from app.services.attachment_service import AttachmentService, to_attachment_read


class ConversationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.nodes = NodeRepository(db)
        self.sessions = SessionRepository(db)
        self.messages = MessageRepository(db)
        self.contexts = ContextRepository(db)
        self.attachments = AttachmentRepository(db)
        self.branches = BranchRepository(db)
        self.attachment_service = AttachmentService(db)

    def _require_node(self, node_id: str):
        node = self.nodes.get_active(node_id)
        if not node:
            raise NotFoundError("NODE_NOT_FOUND", f"Node {node_id} not found")
        return node

    def _require_session(self, session_id: str) -> ConversationSession:
        session = self.sessions.get_active(session_id)
        if not session:
            raise NotFoundError("SESSION_NOT_FOUND", f"Session {session_id} not found")
        return session

    def list_sessions(self, node_id: str) -> list[ConversationSession]:
        self._require_node(node_id)
        return self.sessions.list_active_by_node(node_id)

    def create_session(self, node_id: str, payload: SessionCreate) -> ConversationSession:
        self._require_node(node_id)
        count = self.sessions.count_active_by_node(node_id)
        title = (payload.title or "").strip() or f"会话 {count + 1}"
        session = ConversationSession(id=str(uuid4()), node_id=node_id, title=title)
        self.sessions.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def update_session(self, session_id: str, payload: SessionUpdate) -> ConversationSession:
        session = self._require_session(session_id)
        if payload.title is not None:
            title = payload.title.strip()
            if not title:
                raise AppError("SESSION_TITLE_EMPTY", "Session title cannot be empty", status_code=400)
            session.title = title
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session_id: str) -> None:
        session = self._require_session(session_id)
        self.attachment_service.cleanup_sessions([session_id])
        self.contexts.soft_delete_policy_by_session(session_id)
        self.branches.soft_delete_by_sessions([session_id])
        self.messages.soft_delete_by_sessions([session_id])
        self.sessions.soft_delete(session)
        self.db.commit()

    def list_messages(self, session_id: str) -> list[MessageRead]:
        self._require_session(session_id)
        messages = self.messages.list_visible_by_session(session_id)
        return self._to_message_reads(messages)

    def _to_message_reads(self, messages: list[ChatMessage]) -> list[MessageRead]:
        by_message: dict[str, list] = {m.id: [] for m in messages}
        for attachment in self.attachments.list_by_message_ids(list(by_message)):
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
                provider=getattr(m, "provider", None),
                branch_id=getattr(m, "branch_id", None),
                attachments=by_message.get(m.id, []),
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in messages
        ]

    def create_message(self, session_id: str, payload: MessageCreate) -> MessageRead:
        session = self._require_session(session_id)
        if payload.role == MessageRole.SYSTEM:
            raise AppError("SYSTEM_ROLE_FORBIDDEN", "SYSTEM messages cannot be created by clients", status_code=400)
        content = payload.content.strip()
        if not content:
            raise AppError("MESSAGE_EMPTY", "Message content cannot be empty", status_code=400)

        message = ChatMessage(
            id=str(uuid4()),
            session_id=session.id,
            role=payload.role.value,
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
        self.db.refresh(message)
        return self._to_message_reads([message])[0]

    def update_message(self, message_id: str, payload: MessageUpdate) -> MessageRead:
        message = self.messages.get_visible(message_id)
        if not message:
            raise NotFoundError("MESSAGE_NOT_FOUND", f"Message {message_id} not found")
        content = payload.content.strip()
        if not content:
            raise AppError("MESSAGE_EMPTY", "Message content cannot be empty", status_code=400)

        next_revision = message.current_revision + 1
        self.messages.add_revision(
            MessageRevision(
                id=str(uuid4()),
                message_id=message.id,
                revision_number=next_revision,
                content=content,
            )
        )
        message.content = content
        message.current_revision = next_revision
        message.status = MessageStatus.EDITED.value
        self.db.commit()
        self.db.refresh(message)
        return self._to_message_reads([message])[0]

    def delete_message(self, message_id: str) -> None:
        message = self.messages.get_visible(message_id)
        if not message:
            raise NotFoundError("MESSAGE_NOT_FOUND", f"Message {message_id} not found")
        message.status = MessageStatus.DELETED.value
        self.db.commit()

    def list_revisions(self, message_id: str) -> list[MessageRevision]:
        message = self.messages.get(message_id)
        if not message:
            raise NotFoundError("MESSAGE_NOT_FOUND", f"Message {message_id} not found")
        return self.messages.list_revisions(message_id)
