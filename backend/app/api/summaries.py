from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.summary import SummaryCreate, SummaryUpdate, SummaryVersionRead
from app.services.summary_service import SummaryService

router = APIRouter(tags=["summaries"])


@router.get("/nodes/{node_id}/summary", response_model=SummaryVersionRead | None)
def get_current_summary(node_id: str, db: Session = Depends(db_session)) -> SummaryVersionRead | None:
    return SummaryService(db).get_current(node_id)


@router.post("/nodes/{node_id}/summary", response_model=SummaryVersionRead, status_code=status.HTTP_201_CREATED)
def create_summary(node_id: str, payload: SummaryCreate, db: Session = Depends(db_session)) -> SummaryVersionRead:
    return SummaryService(db).create_version(node_id, payload)


@router.get("/nodes/{node_id}/summary/versions", response_model=list[SummaryVersionRead])
def list_summary_versions(node_id: str, db: Session = Depends(db_session)) -> list[SummaryVersionRead]:
    return SummaryService(db).list_versions(node_id)


@router.post(
    "/nodes/{node_id}/summary/versions/{version_id}/activate",
    response_model=SummaryVersionRead,
)
def activate_summary_version(
    node_id: str,
    version_id: str,
    db: Session = Depends(db_session),
) -> SummaryVersionRead:
    return SummaryService(db).activate_version(node_id, version_id)


@router.patch(
    "/nodes/{node_id}/summary/versions/{version_id}",
    response_model=SummaryVersionRead,
)
def update_summary_version(
    node_id: str,
    version_id: str,
    payload: SummaryUpdate,
    db: Session = Depends(db_session),
) -> SummaryVersionRead:
    return SummaryService(db).update_version(node_id, version_id, payload)


@router.delete(
    "/nodes/{node_id}/summary/versions/{version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_summary_version(
    node_id: str,
    version_id: str,
    db: Session = Depends(db_session),
) -> Response:
    SummaryService(db).delete_version(node_id, version_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
