from datetime import datetime

from app.schemas.common import APIModel, LLMRequestStatus


class StreamMessageCreate(APIModel):
    content: str
    attachment_ids: list[str] = []
    web_search: bool = False
    text_model: str | None = None
    model: str | None = None  # legacy override


class RetryStreamCreate(APIModel):
    """Retry the last user turn in a session (no new user message)."""

    web_search: bool = False
    text_model: str | None = None
    model: str | None = None


class LLMRequestRead(APIModel):
    id: str
    node_id: str
    session_id: str
    user_message_id: str
    assistant_message_id: str | None
    context_snapshot_id: str
    provider: str
    model: str
    status: LLMRequestStatus
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class LLMSettingsRead(APIModel):
    provider: str
    model: str
    search_model: str
    kimi_model: str
    base_url: str
    moonshot_base_url: str
    api_key_configured: bool
    kimi_api_key_configured: bool
    temperature: float
    thinking_enabled: bool
    reasoning_effort: str
    default_text_provider: str
    supports_pdf_text_extract: bool = True
    supports_image_vision: bool = True
    web_search_uses_flash: bool = True
    multimodal_provider: str = "kimi"
