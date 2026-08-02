from datetime import datetime

from app.schemas.attachment import AttachmentRead
from app.schemas.common import APIModel, MessageRole, MessageStatus, TimestampRead


class MessageCreate(APIModel):
    role: MessageRole
    content: str


class MessageUpdate(APIModel):
    content: str


class MessageRead(TimestampRead):
    id: str
    session_id: str
    role: MessageRole
    content: str
    status: MessageStatus
    current_revision: int
    llm_request_id: str | None = None
    provider: str | None = None
    branch_id: str | None = None
    attachments: list[AttachmentRead] = []


class MessageRevisionRead(APIModel):
    id: str
    message_id: str
    revision_number: int
    content: str
    created_at: datetime
