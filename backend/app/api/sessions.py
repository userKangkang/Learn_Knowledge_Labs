from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.session import SessionCreate, SessionRead, SessionUpdate
from app.services.conversation_service import ConversationService

router = APIRouter(tags=["sessions"])


@router.get("/nodes/{node_id}/sessions", response_model=list[SessionRead])
def list_sessions(node_id: str, db: Session = Depends(db_session)) -> list[SessionRead]:
    return ConversationService(db).list_sessions(node_id)


@router.post("/nodes/{node_id}/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(node_id: str, payload: SessionCreate, db: Session = Depends(db_session)) -> SessionRead:
    return ConversationService(db).create_session(node_id, payload)


@router.patch("/sessions/{session_id}", response_model=SessionRead)
def update_session(session_id: str, payload: SessionUpdate, db: Session = Depends(db_session)) -> SessionRead:
    return ConversationService(db).update_session(session_id, payload)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, db: Session = Depends(db_session)) -> Response:
    ConversationService(db).delete_session(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
