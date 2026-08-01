from datetime import datetime

from app.schemas.common import APIModel, ConversationMode, SnapshotSourceType


class SessionSourceCreate(APIModel):
    source_session_id: str
    conversation_mode: ConversationMode
    last_n_turns: int | None = None
    selected_message_ids: list[str] = []
    order_index: int = 0


class SessionSourceRead(APIModel):
    id: str
    source_session_id: str
    conversation_mode: ConversationMode
    last_n_turns: int | None = None
    selected_message_ids: list[str]
    order_index: int


class NodeSourceCreate(APIModel):
    source_node_id: str
    include_summary: bool = False
    order_index: int = 0
    sessions: list[SessionSourceCreate] = []


class NodeSourceRead(APIModel):
    id: str
    source_node_id: str
    include_summary: bool
    order_index: int
    is_same_node: bool
    is_ancestor: bool
    sessions: list[SessionSourceRead]


class ContextPolicyUpdate(APIModel):
    include_current_node_summary: bool = False
    max_context_tokens: int | None = None
    sources: list[NodeSourceCreate] = []


class ContextPolicyRead(APIModel):
    id: str
    session_id: str
    node_id: str
    include_current_node_summary: bool
    include_current_session_history: bool = True  # always true; exposed for UI clarity
    max_context_tokens: int | None
    policy_version: int
    sources: list[NodeSourceRead]
    created_at: datetime
    updated_at: datetime


class CandidateNodeRead(APIModel):
    id: str
    title: str
    node_type: str
    generation: int | None = None


class ContextCandidatesRead(APIModel):
    ancestors: list[CandidateNodeRead]
    non_ancestors: list[CandidateNodeRead]


class ContextPreviewRequest(APIModel):
    new_user_message: str = ""
    persist: bool = False


class SnapshotItemRead(APIModel):
    id: str | None = None
    source_node_id: str | None
    source_session_id: str | None
    source_type: SnapshotSourceType
    source_entity_id: str
    source_version: int
    rendered_content: str
    order_index: int


class ContextPreviewRead(APIModel):
    snapshot_id: str | None = None
    policy_version: int
    rendered_system_prompt: str
    rendered_context: str
    estimated_input_tokens: int
    truncated: bool
    items: list[SnapshotItemRead]
