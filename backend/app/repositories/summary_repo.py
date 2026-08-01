from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.summary import NodeSummaryVersion


class SummaryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active(self, version_id: str) -> NodeSummaryVersion | None:
        stmt = select(NodeSummaryVersion).where(
            NodeSummaryVersion.id == version_id,
            NodeSummaryVersion.deleted_at.is_(None),
        )
        return self.db.scalars(stmt).first()

    def list_active_by_node(self, node_id: str) -> list[NodeSummaryVersion]:
        stmt = (
            select(NodeSummaryVersion)
            .where(NodeSummaryVersion.node_id == node_id, NodeSummaryVersion.deleted_at.is_(None))
            .order_by(NodeSummaryVersion.version_number.desc())
        )
        return list(self.db.scalars(stmt).all())

    def next_version_number(self, node_id: str) -> int:
        stmt = select(func.max(NodeSummaryVersion.version_number)).where(NodeSummaryVersion.node_id == node_id)
        current = self.db.scalar(stmt)
        return (current or 0) + 1

    def add(self, version: NodeSummaryVersion) -> NodeSummaryVersion:
        self.db.add(version)
        self.db.flush()
        return version

    def soft_delete(self, version: NodeSummaryVersion) -> None:
        version.deleted_at = datetime.now(UTC)
        self.db.flush()

    def soft_delete_by_node(self, node_id: str) -> None:
        now = datetime.now(UTC)
        for version in self.list_active_by_node(node_id):
            version.deleted_at = now
        self.db.flush()

    def soft_delete_by_nodes(self, node_ids: list[str]) -> None:
        for node_id in node_ids:
            self.soft_delete_by_node(node_id)
