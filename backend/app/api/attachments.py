from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.attachment import AttachmentRead
from app.services.attachment_service import AttachmentService

router = APIRouter(tags=["attachments"])


@router.post(
    "/sessions/{session_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(db_session),
) -> AttachmentRead:
    data = await file.read()
    return AttachmentService(db).upload(
        session_id,
        filename=file.filename or "upload.pdf",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
