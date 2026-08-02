from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.branch import ConversationBranch


class BranchRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active(self, branch_id: str) -> ConversationBranch | None:
        branch = self.db.get(ConversationBranch, branch_id)
        if not branch or branch.deleted_at is not None:
            return None
        return branch

    def list_active_by_session(self, session_id: str) -> list[ConversationBranch]:
        stmt = (
            select(ConversationBranch)
            .where(
                ConversationBranch.session_id == session_id,
                ConversationBranch.deleted_at.is_(None),
            )
            .order_by(ConversationBranch.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_active_by_anchor(self, anchor_message_id: str) -> list[ConversationBranch]:
        stmt = (
            select(ConversationBranch)
            .where(
                ConversationBranch.anchor_message_id == anchor_message_id,
                ConversationBranch.deleted_at.is_(None),
            )
            .order_by(ConversationBranch.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def add(self, branch: ConversationBranch) -> ConversationBranch:
        self.db.add(branch)
        self.db.flush()
        return branch

    def soft_delete(self, branch: ConversationBranch) -> None:
        branch.deleted_at = datetime.now(UTC)
        self.db.flush()

    def soft_delete_by_sessions(self, session_ids: list[str]) -> None:
        if not session_ids:
            return
        stmt = select(ConversationBranch).where(
            ConversationBranch.session_id.in_(session_ids),
            ConversationBranch.deleted_at.is_(None),
        )
        now = datetime.now(UTC)
        for branch in self.db.scalars(stmt).all():
            branch.deleted_at = now
        self.db.flush()
