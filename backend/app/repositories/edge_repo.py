from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.edge import KnowledgeEdge


class EdgeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active_by_graph(self, graph_id: str) -> list[KnowledgeEdge]:
        stmt = (
            select(KnowledgeEdge)
            .where(KnowledgeEdge.graph_id == graph_id, KnowledgeEdge.deleted_at.is_(None))
            .order_by(KnowledgeEdge.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_active(self, edge_id: str) -> KnowledgeEdge | None:
        stmt = select(KnowledgeEdge).where(
            KnowledgeEdge.id == edge_id,
            KnowledgeEdge.deleted_at.is_(None),
        )
        return self.db.scalars(stmt).first()

    def find_active_duplicate(
        self,
        graph_id: str,
        source_node_id: str,
        target_node_id: str,
        edge_type: str,
        exclude_edge_id: str | None = None,
    ) -> KnowledgeEdge | None:
        stmt = select(KnowledgeEdge).where(
            KnowledgeEdge.graph_id == graph_id,
            KnowledgeEdge.source_node_id == source_node_id,
            KnowledgeEdge.target_node_id == target_node_id,
            KnowledgeEdge.type == edge_type,
            KnowledgeEdge.deleted_at.is_(None),
        )
        if exclude_edge_id:
            stmt = stmt.where(KnowledgeEdge.id != exclude_edge_id)
        return self.db.scalars(stmt).first()

    def count_active_for_node(self, node_id: str) -> int:
        stmt = select(KnowledgeEdge).where(
            KnowledgeEdge.deleted_at.is_(None),
            or_(KnowledgeEdge.source_node_id == node_id, KnowledgeEdge.target_node_id == node_id),
        )
        return len(list(self.db.scalars(stmt).all()))

    def add(self, edge: KnowledgeEdge) -> KnowledgeEdge:
        self.db.add(edge)
        self.db.flush()
        return edge

    def soft_delete(self, edge: KnowledgeEdge) -> None:
        edge.deleted_at = datetime.now(UTC)
        self.db.flush()

    def soft_delete_by_graph(self, graph_id: str) -> None:
        now = datetime.now(UTC)
        for edge in self.list_active_by_graph(graph_id):
            edge.deleted_at = now
        self.db.flush()
