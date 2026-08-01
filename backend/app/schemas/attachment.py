from datetime import datetime

from app.schemas.common import APIModel, AttachmentExtractStatus


class AttachmentRead(APIModel):
    id: str
    session_id: str
    message_id: str | None
    filename: str
    content_type: str
    kind: str = "pdf"
    size_bytes: int
    extract_status: AttachmentExtractStatus
    extract_error: str | None = None
    has_extracted_text: bool = False
    created_at: datetime
