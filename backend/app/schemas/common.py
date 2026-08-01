from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NodeType(StrEnum):
    TOPIC = "TOPIC"
    CONCEPT = "CONCEPT"
    THEORY = "THEORY"
    METHOD = "METHOD"
    QUESTION = "QUESTION"
    EXAMPLE = "EXAMPLE"
    APPLICATION = "APPLICATION"


class EdgeType(StrEnum):
    IS_A = "IS_A"
    PART_OF = "PART_OF"
    PREREQUISITE_OF = "PREREQUISITE_OF"
    EXAMPLE_OF = "EXAMPLE_OF"
    CAUSES_OR_LEADS_TO = "CAUSES_OR_LEADS_TO"
    CONTRASTS_WITH = "CONTRASTS_WITH"
    APPLIES_TO = "APPLIES_TO"
    CUSTOM = "CUSTOM"


class AuthorType(StrEnum):
    USER = "USER"
    LLM = "LLM"
    LLM_AND_USER = "LLM_AND_USER"


class MessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class MessageStatus(StrEnum):
    ACTIVE = "ACTIVE"
    EDITED = "EDITED"
    DELETED = "DELETED"
    STREAMING = "STREAMING"
    FAILED = "FAILED"


class LLMRequestStatus(StrEnum):
    PENDING = "PENDING"
    STREAMING = "STREAMING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AttachmentExtractStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ConversationMode(StrEnum):
    NONE = "NONE"
    LAST_N_TURNS = "LAST_N_TURNS"
    SELECTED_MESSAGES = "SELECTED_MESSAGES"
    FULL_SESSION = "FULL_SESSION"


class SnapshotSourceType(StrEnum):
    CURRENT_NODE_SUMMARY = "CURRENT_NODE_SUMMARY"
    BORROWED_NODE_SUMMARY = "BORROWED_NODE_SUMMARY"
    CURRENT_SESSION_MESSAGE = "CURRENT_SESSION_MESSAGE"
    BORROWED_SESSION_MESSAGE = "BORROWED_SESSION_MESSAGE"
    SAME_NODE_SESSION_MESSAGE = "SAME_NODE_SESSION_MESSAGE"
    NEW_USER_MESSAGE = "NEW_USER_MESSAGE"
    NODE_META = "NODE_META"


class TimestampRead(APIModel):
    created_at: datetime
    updated_at: datetime
