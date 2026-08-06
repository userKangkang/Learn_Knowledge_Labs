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

    llm_temperature: float = 0.2
    llm_thinking_enabled: bool = True
    llm_reasoning_effort: str = "high"
    default_text_provider: str = "deepseek"  # deepseek | kimi
    upload_dir: str = str(DEFAULT_UPLOAD_DIR)
    max_upload_bytes: int = 20 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
