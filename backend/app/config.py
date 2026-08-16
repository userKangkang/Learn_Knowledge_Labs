from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "knowledge_labs.db"
DEFAULT_UPLOAD_DIR = BACKEND_DIR / "data" / "uploads"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Knowledge Labs API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    deepseek_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("DEEPSEEK_API_KEY", "DEEPSEEK_API", "deepseek_api_key"),
    )
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_search_model: str = "deepseek-v4-flash"

    moonshot_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("MOONSHOT_API_KEY", "KIMI_API_KEY", "moonshot_api_key"),
    )
    moonshot_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "kimi-k3"

    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("CHATGPT_API_KEY", "OPENAI_API_KEY", "openai_api_key"),
    )
    openai_base_url: str = Field(
        default="https://zctotoken.com/v1",
        validation_alias=AliasChoices("CHATGPT_BASE_URL", "OPENAI_BASE_URL", "openai_base_url"),
    )
    openai_model: str = Field(
        default="gpt-5.6-terra",
        validation_alias=AliasChoices("CHATGPT_MODEL", "OPENAI_MODEL", "openai_model"),
    )

    llm_temperature: float = 0.2
    llm_thinking_enabled: bool = True
    llm_reasoning_effort: str = "high"
    default_text_provider: str = "deepseek"  # deepseek | kimi | openai
    related_paper_search_max_context_tokens: int = 32000
    upload_dir: str = str(DEFAULT_UPLOAD_DIR)
    max_upload_bytes: int = 20 * 1024 * 1024
    # PDF slides are rendered into visual inputs for Kimi in file-digest mode.
    pdf_visual_max_pages: int = 24
    pdf_visual_max_edge: int = 1600
    pdf_visual_jpeg_quality: int = 72


@lru_cache
def get_settings() -> Settings:
    return Settings()
