from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attachment import MessageAttachment


class AttachmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active(self, attachment_id: str) -> MessageAttachment | None:
        attachment = self.db.get(MessageAttachment, attachment_id)
        if not attachment or attachment.deleted_at is not None:
            return None
        return attachment

    def list_active_by_ids(self, attachment_ids: list[str]) -> list[MessageAttachment]:
        if not attachment_ids:
            return []
        stmt = select(MessageAttachment).where(
            MessageAttachment.id.in_(attachment_ids),
            MessageAttachment.deleted_at.is_(None),
        )
        found = {a.id: a for a in self.db.scalars(stmt).all()}
        return [found[i] for i in attachment_ids if i in found]

    def list_by_message_ids(self, message_ids: list[str]) -> list[MessageAttachment]:
        if not message_ids:
            return []
        stmt = (
            select(MessageAttachment)
            .where(
                MessageAttachment.message_id.in_(message_ids),
                MessageAttachment.deleted_at.is_(None),
            )
            .order_by(MessageAttachment.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def add(self, attachment: MessageAttachment) -> MessageAttachment:
        self.db.add(attachment)
        self.db.flush()
        return attachment

    def soft_delete(self, attachment: MessageAttachment) -> None:
        attachment.deleted_at = datetime.now(UTC)
        self.db.flush()
