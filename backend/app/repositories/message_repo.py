from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import ChatMessage, MessageRevision
from app.schemas.common import MessageStatus


class MessageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_visible_by_session(self, session_id: str) -> list[ChatMessage]:
        """Mainline messages only (side branches are excluded from the primary thread)."""
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.status != MessageStatus.DELETED.value,
                ChatMessage.branch_id.is_(None),
            )
            .order_by(ChatMessage.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_visible_by_branch(self, branch_id: str) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.branch_id == branch_id,
                ChatMessage.status != MessageStatus.DELETED.value,
            )
            .order_by(ChatMessage.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_mainline_upto(self, session_id: str, anchor_message_id: str) -> list[ChatMessage]:
        messages = self.list_visible_by_session(session_id)
        result: list[ChatMessage] = []
        for message in messages:
            result.append(message)
            if message.id == anchor_message_id:
                return result
        return []

    def get(self, message_id: str) -> ChatMessage | None:
        return self.db.get(ChatMessage, message_id)

    def get_visible(self, message_id: str) -> ChatMessage | None:
        message = self.get(message_id)
        if not message or message.status == MessageStatus.DELETED.value:
            return None
        return message

    def add(self, message: ChatMessage) -> ChatMessage:
        self.db.add(message)
        self.db.flush()
        return message

    def add_revision(self, revision: MessageRevision) -> MessageRevision:
        self.db.add(revision)
        self.db.flush()
        return revision

    def list_revisions(self, message_id: str) -> list[MessageRevision]:
        stmt = (
            select(MessageRevision)
            .where(MessageRevision.message_id == message_id)
            .order_by(MessageRevision.revision_number.asc())
        )
        return list(self.db.scalars(stmt).all())

    def soft_delete_by_sessions(self, session_ids: list[str]) -> None:
        if not session_ids:
            return
        stmt = select(ChatMessage).where(
            ChatMessage.session_id.in_(session_ids),
            ChatMessage.status != MessageStatus.DELETED.value,
        )
        for message in self.db.scalars(stmt).all():
            message.status = MessageStatus.DELETED.value
        self.db.flush()
