from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.context import (
    ContextCandidatesRead,
    ContextPolicyRead,
    ContextPolicyUpdate,
    ContextPreviewRead,
    ContextPreviewRequest,
)
from app.services.context_builder import ContextBuilder
from app.services.context_policy_service import ContextPolicyService

router = APIRouter(tags=["contexts"])


@router.get("/sessions/{session_id}/context-policy", response_model=ContextPolicyRead)
def get_context_policy(session_id: str, db: Session = Depends(db_session)) -> ContextPolicyRead:
    return ContextPolicyService(db).get_policy(session_id)


@router.put("/sessions/{session_id}/context-policy", response_model=ContextPolicyRead)
def put_context_policy(
    session_id: str,
    payload: ContextPolicyUpdate,
    db: Session = Depends(db_session),
) -> ContextPolicyRead:
    return ContextPolicyService(db).replace_policy(session_id, payload)


@router.get("/sessions/{session_id}/context-candidates", response_model=ContextCandidatesRead)
def get_context_candidates(session_id: str, db: Session = Depends(db_session)) -> ContextCandidatesRead:
    return ContextPolicyService(db).list_candidates(session_id)


@router.post("/sessions/{session_id}/context-preview", response_model=ContextPreviewRead)
def preview_context(
    session_id: str,
    payload: ContextPreviewRequest,
    db: Session = Depends(db_session),
) -> ContextPreviewRead:
    return ContextBuilder(db).preview(
        session_id,
        payload.new_user_message,
        persist=payload.persist,
    )
