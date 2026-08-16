"""Resolve user-facing text model choices to configured providers."""

from app.errors import AppError


def default_text_model(settings) -> str:
    provider = (settings.default_text_provider or "deepseek").strip().lower()
    if provider == "kimi":
        return settings.kimi_model.strip()
    if provider == "openai":
        return settings.openai_model.strip()
    return settings.deepseek_model.strip()


def resolve_text_route(
    *,
    text_model: str | None,
    model: str | None = None,
    web_search: bool,
    settings,
    file_mode: bool = False,
) -> tuple[str, str, bool]:
    """Return provider, configured model id, and effective web-search flag."""
    if file_mode:
        return "kimi", settings.kimi_model.strip(), False

    choice = (text_model or model or default_text_model(settings)).strip()
    if choice == settings.kimi_model.strip() or choice.startswith("kimi"):
        return "kimi", settings.kimi_model.strip(), web_search
    if choice == settings.openai_model.strip() or choice.startswith(("gpt-", "chatgpt-", "o1", "o3", "o4")):
        return "openai", settings.openai_model.strip(), web_search
    if choice in {settings.deepseek_model.strip(), settings.deepseek_search_model.strip()} or choice.startswith("deepseek"):
        model_id = settings.deepseek_search_model.strip() if web_search else settings.deepseek_model.strip()
        return "deepseek", model_id, web_search
    raise AppError("TEXT_MODEL_INVALID", "所选文本模型不属于当前配置的 DeepSeek、Kimi 或 OpenAI 模型", status_code=400)
