from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.context import (
    ContextNodeSource,
    ContextSessionSource,
    ContextSnapshot,
    ContextSnapshotItem,
    SessionContextPolicy,
)


class ContextRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_policy_by_session(self, session_id: str) -> SessionContextPolicy | None:
        stmt = (
            select(SessionContextPolicy)
            .where(SessionContextPolicy.session_id == session_id, SessionContextPolicy.deleted_at.is_(None))
            .options(
                selectinload(SessionContextPolicy.node_sources).selectinload(ContextNodeSource.session_sources)
            )
        )
        return self.db.scalars(stmt).first()

    def add_policy(self, policy: SessionContextPolicy) -> SessionContextPolicy:
        self.db.add(policy)
        self.db.flush()
        return policy

    def soft_delete_sources_for_policy(self, policy_id: str) -> None:
        now = datetime.now(UTC)
        sources = self.db.scalars(
            select(ContextNodeSource).where(
                ContextNodeSource.context_policy_id == policy_id,
                ContextNodeSource.deleted_at.is_(None),
            )
        ).all()
        for source in sources:
            source.deleted_at = now
            for session_source in source.session_sources:
                if session_source.deleted_at is None:
                    session_source.deleted_at = now
        self.db.flush()

    def add_node_source(self, source: ContextNodeSource) -> ContextNodeSource:
        self.db.add(source)
        self.db.flush()
        return source

    def add_session_source(self, source: ContextSessionSource) -> ContextSessionSource:
        self.db.add(source)
        self.db.flush()
        return source

    def list_active_node_sources(self, policy_id: str) -> list[ContextNodeSource]:
        stmt = (
            select(ContextNodeSource)
            .where(
                ContextNodeSource.context_policy_id == policy_id,
                ContextNodeSource.deleted_at.is_(None),
            )
            .options(selectinload(ContextNodeSource.session_sources))
            .order_by(ContextNodeSource.order_index.asc())
        )
        sources = list(self.db.scalars(stmt).all())
        for source in sources:
            source.session_sources = sorted(
                [s for s in source.session_sources if s.deleted_at is None],
                key=lambda s: s.order_index,
            )
        return sources

    def soft_delete_policy_by_session(self, session_id: str) -> None:
        policy = self.get_policy_by_session(session_id)
        if not policy:
            return
        self.soft_delete_sources_for_policy(policy.id)
        policy.deleted_at = datetime.now(UTC)
        self.db.flush()

    def soft_delete_policies_by_sessions(self, session_ids: list[str]) -> None:
        for session_id in session_ids:
            self.soft_delete_policy_by_session(session_id)

    def add_snapshot(self, snapshot: ContextSnapshot) -> ContextSnapshot:
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def add_snapshot_item(self, item: ContextSnapshotItem) -> ContextSnapshotItem:
        self.db.add(item)
        self.db.flush()
        return item
