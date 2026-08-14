from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError, NotFoundError
from app.models.attachment import MessageAttachment
from app.repositories.attachment_repo import AttachmentRepository
from app.repositories.session_repo import SessionRepository
from app.schemas.attachment import AttachmentRead
from app.schemas.common import AttachmentExtractStatus
from app.services.pdf_extract import extract_pdf_text
from app.services.uploads import safe_remove_upload

ALLOWED_PDF_TYPES = {"application/pdf", "application/x-pdf"}
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def to_attachment_read(attachment: MessageAttachment) -> AttachmentRead:
    return AttachmentRead(
        id=attachment.id,
        session_id=attachment.session_id,
        message_id=attachment.message_id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        extract_status=AttachmentExtractStatus(attachment.extract_status),
        extract_error=attachment.extract_error,
        has_extracted_text=bool(attachment.extracted_text),
        created_at=attachment.created_at,
        kind=getattr(attachment, "kind", None) or ("image" if attachment.content_type.startswith("image/") else "pdf"),
    )


class AttachmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.sessions = SessionRepository(db)
        self.attachments = AttachmentRepository(db)
        self.settings = get_settings()

    def upload(self, session_id: str, *, filename: str, content_type: str, data: bytes) -> AttachmentRead:
        session = self.sessions.get_active(session_id)
        if not session:
            raise NotFoundError("SESSION_NOT_FOUND", f"Session {session_id} not found")

        name = (filename or "upload.bin").strip() or "upload.bin"
        ctype = (content_type or "").split(";")[0].strip().lower() or "application/octet-stream"
        suffix = Path(name).suffix.lower()
        is_pdf = suffix == ".pdf" or ctype in ALLOWED_PDF_TYPES
        is_image = suffix in IMAGE_SUFFIXES or ctype in ALLOWED_IMAGE_TYPES
        if not is_pdf and not is_image:
            raise AppError(
                "ATTACHMENT_TYPE_UNSUPPORTED",
                "仅支持 PDF 与常见图片（png/jpeg/webp/gif）。多模态解析将使用 Kimi。",
                status_code=400,
            )
        if len(data) <= 0:
            raise AppError("ATTACHMENT_EMPTY", "上传文件为空", status_code=400)
        if len(data) > self.settings.max_upload_bytes:
            raise AppError(
                "ATTACHMENT_TOO_LARGE",
                f"文件超过大小限制（{self.settings.max_upload_bytes} bytes）",
                status_code=400,
            )

        attachment_id = str(uuid4())
        upload_root = Path(self.settings.upload_dir) / session_id
        upload_root.mkdir(parents=True, exist_ok=True)

        if is_image:
            ext = suffix if suffix in IMAGE_SUFFIXES else ".png"
            storage_path = upload_root / f"{attachment_id}{ext}"
            storage_path.write_bytes(data)
            if ctype not in ALLOWED_IMAGE_TYPES:
                ctype = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".webp": "image/webp",
                    ".gif": "image/gif",
                    ".bmp": "image/bmp",
                }.get(ext, "image/png")
            attachment = MessageAttachment(
                id=attachment_id,
                session_id=session_id,
                message_id=None,
                filename=name,
                content_type=ctype,
                kind="image",
                size_bytes=len(data),
                storage_path=str(storage_path),
                extracted_text=None,
                extract_status=AttachmentExtractStatus.SKIPPED.value,
                extract_error=None,
            )
        else:
            storage_path = upload_root / f"{attachment_id}.pdf"
            storage_path.write_bytes(data)
            extracted_text: str | None = None
            extract_status = AttachmentExtractStatus.SUCCEEDED.value
            extract_error: str | None = None
            try:
                extracted_text = extract_pdf_text(storage_path)
                if not extracted_text:
                    extract_status = AttachmentExtractStatus.FAILED.value
                    extract_error = "未能从 PDF 提取到文本（扫描版请改上传页面截图，由 Kimi 读图）"
                    extracted_text = None
            except Exception as error:  # noqa: BLE001
                extract_status = AttachmentExtractStatus.FAILED.value
                extract_error = f"PDF 解析失败：{error}"
                extracted_text = None
            attachment = MessageAttachment(
                id=attachment_id,
                session_id=session_id,
                message_id=None,
                filename=name,
                content_type="application/pdf",
                kind="pdf",
                size_bytes=len(data),
                storage_path=str(storage_path),
                extracted_text=extracted_text,
                extract_status=extract_status,
                extract_error=extract_error,
            )

        self.attachments.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)
        return to_attachment_read(attachment)

    def bind_to_message(self, attachment_ids: list[str], *, session_id: str, message_id: str) -> list[MessageAttachment]:
        items = self.attachments.list_active_by_ids(attachment_ids)
        if len(items) != len(attachment_ids):
            raise AppError("ATTACHMENT_NOT_FOUND", "部分附件不存在或已删除", status_code=404)
        for item in items:
            if item.session_id != session_id:
                raise AppError("ATTACHMENT_SESSION_MISMATCH", "附件不属于当前会话", status_code=400)
            if item.message_id is not None and item.message_id != message_id:
                raise AppError("ATTACHMENT_ALREADY_BOUND", "附件已绑定到其他消息", status_code=409)
            item.message_id = message_id
        self.db.flush()
        return items

    def cleanup_sessions(self, session_ids: list[str]) -> None:
        """Soft-delete attachments of the given sessions and remove their files."""
        if not session_ids:
            return
        attachments = self.attachments.list_by_session_ids(session_ids)
        for attachment in attachments:
            safe_remove_upload(attachment.storage_path)
        self.attachments.soft_delete_many(attachments)
