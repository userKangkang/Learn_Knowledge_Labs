from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.session import ConversationSession


class SessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active_by_node(self, node_id: str) -> list[ConversationSession]:
        stmt = (
            select(ConversationSession)
            .where(ConversationSession.node_id == node_id, ConversationSession.deleted_at.is_(None))
            .order_by(ConversationSession.updated_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_active(self, session_id: str) -> ConversationSession | None:
        stmt = select(ConversationSession).where(
            ConversationSession.id == session_id,
            ConversationSession.deleted_at.is_(None),
        )
        return self.db.scalars(stmt).first()

    def count_active_by_node(self, node_id: str) -> int:
        return len(self.list_active_by_node(node_id))

    def add(self, session: ConversationSession) -> ConversationSession:
        self.db.add(session)
        self.db.flush()
        return session

    def soft_delete(self, session: ConversationSession) -> None:
        session.deleted_at = datetime.now(UTC)
        self.db.flush()

    def soft_delete_by_node(self, node_id: str) -> list[str]:
        now = datetime.now(UTC)
        ids: list[str] = []
        for session in self.list_active_by_node(node_id):
            session.deleted_at = now
            ids.append(session.id)
        self.db.flush()
        return ids
