"""Paper document upload, PDF text extraction, and optional Kimi detailed reading."""

import base64
from pathlib import Path
from uuid import uuid4

from app.errors import AppError
from app.models.paper_study import PaperStudyDocument
from app.schemas.paper_study import PaperDocumentRead, PaperSourceTextPreviewRead, PaperStudyRead
from app.services.paper_study.base import PaperStudyServiceBase
from app.services.paper_study.prompts import KIMI_DETAILED_READING_PROMPT
from app.services.pdf_extract import extract_pdf_text

ALLOWED_PDF_TYPES = {"application/pdf", "application/x-pdf"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


class PaperDocumentService(PaperStudyServiceBase):
    def upload_document(self, study_id: str, *, filename: str, content_type: str, data: bytes) -> PaperDocumentRead:
        study = self._require_study(study_id)
        if self.repo.get_document(study.id):
            raise AppError("PAPER_ALREADY_EXISTS", "当前论文理解记录已有论文；请新建记录以更换论文", status_code=409)
        name = (filename or "paper.pdf").strip() or "paper.pdf"
        content_type = (content_type or "").split(";", 1)[0].lower()
        suffix = Path(name).suffix.lower()
        is_pdf = suffix == ".pdf" or content_type in ALLOWED_PDF_TYPES
        is_image = suffix in IMAGE_SUFFIXES or content_type in ALLOWED_IMAGE_TYPES
        if not is_pdf and not is_image:
            raise AppError("PAPER_TYPE_UNSUPPORTED", "仅支持 PDF 或常见图片", status_code=400)
        if not data or len(data) > self.settings.max_upload_bytes:
            raise AppError("PAPER_UPLOAD_INVALID", "文件为空或超过大小限制", status_code=400)
        document_id = str(uuid4())
        folder = Path(self.settings.upload_dir) / "paper-studies" / study.id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{document_id}{'.pdf' if is_pdf else suffix}"
        path.write_bytes(data)
        extracted = None
        if is_pdf:
            try:
                extracted = extract_pdf_text(path) or None
            except Exception:  # Kimi still is the primary parser.
                pass
        document = PaperStudyDocument(
            id=document_id, study_id=study.id, filename=name, content_type="application/pdf" if is_pdf else content_type,
            size_bytes=len(data), storage_path=str(path), extracted_text=extracted,
        )
        self.repo.add(document)
        self.db.commit()
        self.db.refresh(document)
        return self._document_read(document)

    def source_text_preview(self, study_id: str) -> PaperSourceTextPreviewRead:
        study = self._require_study(study_id)
        document = self.repo.get_document(study.id)
        if not document or not (document.extracted_text or "").strip():
            raise AppError("PAPER_SOURCE_TEXT_UNAVAILABLE", "当前 PDF 没有可预览的直接提取文本", status_code=409)
        return PaperSourceTextPreviewRead(
            filename=document.filename,
            content=document.extracted_text,
            character_count=len(document.extracted_text),
            extraction_note="这是从 PDF 直接提取的原始文字，不是模型解读；请检查是否有缺页、乱码、断行或阅读顺序问题。",
        )

    def analyze_document(self, study_id: str) -> PaperStudyRead:
        study = self._require_study(study_id)
        document = self.repo.get_document(study.id)
        if not document:
            raise AppError("PAPER_REQUIRED", "请先上传论文", status_code=400)
        self.gateway.require_provider("kimi")
        document.status = "ANALYZING"
        document.error = None
        self.db.commit()
        try:
            if document.content_type == "application/pdf":
                try:
                    extracted = self.gateway.extract_kimi_file(path=document.storage_path, filename=document.filename, content_type=document.content_type)
                except AppError:
                    extracted = document.extracted_text or ""
                if not extracted.strip():
                    raise AppError("PAPER_EXTRACT_EMPTY", "无法从论文中提取正文", status_code=502)
                messages = [{"role": "user", "content": f"论文：{document.filename}\n\n正文：\n{extracted}"}]
            else:
                encoded = base64.b64encode(Path(document.storage_path).read_bytes()).decode("ascii")
                messages = [{"role": "user", "content": [{"type": "text", "text": "请解读这张论文页面"}, {"type": "image_url", "image_url": {"url": f"data:{document.content_type};base64,{encoded}"}}]}]
            document.kimi_detailed_analysis = self._collect(
                provider="kimi", model=self.settings.kimi_model.strip(),
                system=KIMI_DETAILED_READING_PROMPT, messages=messages,
            )
            document.status = "READY"
            self.db.commit()
        except AppError as error:
            document.status = "FAILED"
            document.error = error.message
            self.db.commit()
            raise
        return self._study_read(study)
