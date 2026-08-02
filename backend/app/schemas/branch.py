from datetime import datetime
from typing import Literal

from app.schemas.common import APIModel, MessageRole
from app.schemas.llm import TextModelChoice
from app.schemas.message import MessageRead


class TempTurn(APIModel):
    role: Literal["USER", "ASSISTANT"]
    content: str


class EphemeralStreamCreate(APIModel):
    """Ephemeral side chat: no ChatMessage rows are persisted."""

    anchor_message_id: str
    content: str
    prior_turns: list[TempTurn] = []
    web_search: bool = False
    text_model: TextModelChoice | None = None


class BranchCreate(APIModel):
    """Persist a completed (or in-progress) temp chat as a side branch under an assistant message."""

    anchor_message_id: str
    turns: list[TempTurn]
    title: str | None = None


class BranchStreamCreate(APIModel):
    content: str
    web_search: bool = False
    text_model: TextModelChoice | None = None


class BranchRead(APIModel):
    id: str
    session_id: str
    anchor_message_id: str
    title: str | None = None
    message_count: int = 0
    created_at: datetime
    messages: list[MessageRead] = []
