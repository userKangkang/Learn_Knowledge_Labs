from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

from app.models.attachment import MessageAttachment
from app.models.message import ChatMessage
from app.services.llm_prompts import DEFAULT_FILE_DIGEST_USER_HINT


def message_text_for_provider(message: ChatMessage, *, target_provider: str) -> str:
    """Cross-vendor: final content only. Same-vendor: may append vendor_meta notes."""
    text = message.content or ""
    if message.provider and message.provider == target_provider and message.vendor_meta:
        try:
            meta = json.loads(message.vendor_meta)
        except json.JSONDecodeError:
            meta = None
        if isinstance(meta, dict):
            extra = meta.get("same_vendor_notes")
            if isinstance(extra, str) and extra.strip():
                text = f"{text}\n\n{extra.strip()}"
    return text


def build_transcript_messages(
    history: list[ChatMessage],
    *,
    target_provider: str,
    exclude_message_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    excluded = exclude_message_ids or set()
    out: list[dict[str, Any]] = []
    for message in history:
        if message.id in excluded:
            continue
        if message.role not in {"USER", "ASSISTANT"}:
            continue
        if message.status in {"DELETED"}:
            continue
        if message.status == "STREAMING" and not (message.content or "").strip():
            continue
        if message.status == "FAILED" and not (message.content or "").strip():
            continue
        body = message_text_for_provider(message, target_provider=target_provider).strip()
        if not body:
            continue
        out.append({"role": message.role.lower(), "content": body})
    return out


def _image_data_url(path: Path, content_type: str) -> str:
    mime = content_type or mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def build_file_digest_user_content(
    *,
    user_text: str,
    attachments: list[MessageAttachment],
) -> tuple[str | list[dict[str, Any]], bool]:
    """
    Returns (content, has_visual_parts).
    Visual images go as multimodal parts for Kimi; PDF text is inlined as text.
    """
    text = (user_text or "").strip() or DEFAULT_FILE_DIGEST_USER_HINT
    image_parts: list[dict[str, Any]] = []
    pdf_blocks: list[str] = []

    for attachment in attachments:
        kind = (attachment.kind or "pdf").lower()
        if kind == "image":
            path = Path(attachment.storage_path)
            if path.is_file():
                image_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": _image_data_url(path, attachment.content_type)},
                    }
                )
            else:
                pdf_blocks.append(f"[图片缺失] {attachment.filename}")
        else:
            if attachment.extracted_text:
                pdf_blocks.append(f"[PDF·{attachment.filename}]\n{attachment.extracted_text}")
            else:
                pdf_blocks.append(
                    f"[PDF·{attachment.filename}]（本地未能抽到文本；请结合文件名说明局限，"
                    f"并提示用户可改为上传页面截图以便视觉解析）"
                )

    text_body = text
    if pdf_blocks:
        text_body = text + "\n\n" + "\n\n".join(pdf_blocks)

    if not image_parts:
        return text_body, False

    parts: list[dict[str, Any]] = [*image_parts, {"type": "text", "text": text_body}]
    return parts, True
