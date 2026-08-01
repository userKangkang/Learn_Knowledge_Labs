from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.message import MessageCreate, MessageRead, MessageRevisionRead, MessageUpdate
from app.services.conversation_service import ConversationService

router = APIRouter(tags=["messages"])


@router.get("/sessions/{session_id}/messages", response_model=list[MessageRead])
def list_messages(session_id: str, db: Session = Depends(db_session)) -> list[MessageRead]:
    return ConversationService(db).list_messages(session_id)


@router.post("/sessions/{session_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def create_message(session_id: str, payload: MessageCreate, db: Session = Depends(db_session)) -> MessageRead:
    return ConversationService(db).create_message(session_id, payload)


@router.patch("/messages/{message_id}", response_model=MessageRead)
def update_message(message_id: str, payload: MessageUpdate, db: Session = Depends(db_session)) -> MessageRead:
    return ConversationService(db).update_message(message_id, payload)


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(message_id: str, db: Session = Depends(db_session)) -> Response:
    ConversationService(db).delete_message(message_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/messages/{message_id}/revisions", response_model=list[MessageRevisionRead])
def list_revisions(message_id: str, db: Session = Depends(db_session)) -> list[MessageRevisionRead]:
    return ConversationService(db).list_revisions(message_id)
