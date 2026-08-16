from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.models.attachment import MessageAttachment
from app.models.message import ChatMessage
from app.services.llm_prompts import DEFAULT_FILE_DIGEST_USER_HINT
from app.services.pdf_visuals import render_pdf_pages_as_data_urls


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
    settings: Settings | None = None,
) -> tuple[str | list[dict[str, Any]], bool]:
    """Build Kimi's file-digest input with both extracted text and visual parts."""
    settings = settings or get_settings()
    text = (user_text or "").strip() or DEFAULT_FILE_DIGEST_USER_HINT
    visual_parts: list[dict[str, Any]] = []
    pdf_blocks: list[str] = []

    for attachment in attachments:
        kind = (attachment.kind or "pdf").lower()
        if kind == "image":
            path = Path(attachment.storage_path)
            if path.is_file():
                visual_parts.extend(
                    [
                        {"type": "text", "text": f"[图片附件视觉输入：{attachment.filename}]"},
                        {
                            "type": "image_url",
                            "image_url": {"url": _image_data_url(path, attachment.content_type)},
                        },
                    ]
                )
            else:
                pdf_blocks.append(f"[图片缺失] {attachment.filename}")
            continue

        if attachment.extracted_text:
            pdf_blocks.append(f"[PDF·{attachment.filename}]\n{attachment.extracted_text}")
        else:
            pdf_blocks.append(
                f"[PDF·{attachment.filename}]（本地未能抽取文本；请结合页面视觉输入说明局限，"
                "必要时提示用户改上传页面截图。）"
            )

        path = Path(attachment.storage_path)
        if not path.is_file():
            continue

        visual_pages, page_count = render_pdf_pages_as_data_urls(
            path,
            max_pages=settings.pdf_visual_max_pages,
            max_edge=settings.pdf_visual_max_edge,
            jpeg_quality=settings.pdf_visual_jpeg_quality,
        )
        if not visual_pages:
            pdf_blocks.append(
                f"[PDF视觉输入提示：{attachment.filename}] 本轮未能生成页面图像；"
                "如果原文包含重要图表，请另行上传页面截图。"
            )
            continue

        pdf_blocks.append(
            f"[PDF视觉输入：{attachment.filename}] 已附上第 1-{len(visual_pages)} 页页面图像；"
            "请结合页面布局、图表、公式和图片进行解析。"
        )
        if page_count > len(visual_pages):
            pdf_blocks.append(
                f"[PDF视觉输入提示：{attachment.filename}] 共 {page_count} 页，"
                f"本轮仅附上前 {len(visual_pages)} 页页面图像。"
            )

        for page_number, data_url in visual_pages:
            visual_parts.extend(
                [
                    {
                        "type": "text",
                        "text": f"[PDF页面视觉输入：{attachment.filename} · 第 {page_number} 页]",
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]
            )

    text_body = text
    if pdf_blocks:
        text_body = text + "\n\n" + "\n\n".join(pdf_blocks)

    if not visual_parts:
        return text_body, False

    parts: list[dict[str, Any]] = [{"type": "text", "text": text_body}, *visual_parts]
    return parts, True
