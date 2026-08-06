"""Shared helpers for the paper-understanding workflow."""

import json

from app.errors import AppError


def paper_sse(event: str, data: dict) -> str:
    """Frame one Server-Sent Events message."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def clean_json(text: str) -> dict:
    """Parse strict model JSON, tolerating fenced code blocks or stray prose."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:-1]).strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise AppError("LLM_JSON_INVALID", "模型没有返回可解析的 JSON", status_code=502)
        try:
            value = json.loads(raw[start : end + 1])
        except json.JSONDecodeError as error:
            raise AppError("LLM_JSON_INVALID", "模型返回的 JSON 格式无效", status_code=502) from error
    if not isinstance(value, dict):
        raise AppError("LLM_JSON_INVALID", "模型返回的顶层 JSON 必须是对象", status_code=502)
    return value
