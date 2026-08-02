from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.branch import BranchCreate, BranchRead, BranchStreamCreate, EphemeralStreamCreate
from app.services.temp_chat_service import TempChatService

router = APIRouter(tags=["temp-chats"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.get("/sessions/{session_id}/branches", response_model=list[BranchRead])
def list_branches(
    session_id: str,
    anchor_message_id: str | None = None,
    db: Session = Depends(db_session),
) -> list[BranchRead]:
    return TempChatService(db).list_branches(session_id, anchor_message_id=anchor_message_id)


@router.get("/branches/{branch_id}", response_model=BranchRead)
def get_branch(branch_id: str, db: Session = Depends(db_session)) -> BranchRead:
    return TempChatService(db).get_branch(branch_id)


@router.post("/sessions/{session_id}/branches", response_model=BranchRead, status_code=status.HTTP_201_CREATED)
def create_branch(
    session_id: str,
    payload: BranchCreate,
    db: Session = Depends(db_session),
) -> BranchRead:
    return TempChatService(db).create_branch(session_id, payload)


@router.delete("/branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch(branch_id: str, db: Session = Depends(db_session)) -> Response:
    TempChatService(db).delete_branch(branch_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/temp-chats/ephemeral/stream")
def stream_ephemeral(
    session_id: str,
    payload: EphemeralStreamCreate,
    db: Session = Depends(db_session),
) -> StreamingResponse:
    service = TempChatService(db)
    prepared = service.prepare_ephemeral(session_id, payload)
    return StreamingResponse(service.stream(prepared), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/branches/{branch_id}/messages/stream")
def stream_branch_message(
    branch_id: str,
    payload: BranchStreamCreate,
    db: Session = Depends(db_session),
) -> StreamingResponse:
    service = TempChatService(db)
    prepared = service.prepare_branch_stream(branch_id, payload)
    return StreamingResponse(service.stream(prepared), media_type="text/event-stream", headers=_SSE_HEADERS)
