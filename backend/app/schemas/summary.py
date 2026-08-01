from datetime import datetime

from app.schemas.common import APIModel, AuthorType


class SummaryCreate(APIModel):
    content: str


class SummaryUpdate(APIModel):
    content: str


class SummaryVersionRead(APIModel):
    id: str
    node_id: str
    version_number: int
    content: str
    author_type: AuthorType
    generated_from_message_ids: list[str]
    created_at: datetime
    is_current: bool = False
