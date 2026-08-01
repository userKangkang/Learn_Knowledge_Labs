from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.node import KnowledgeNode


class NodeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active_by_graph(self, graph_id: str) -> list[KnowledgeNode]:
        stmt = (
            select(KnowledgeNode)
            .where(KnowledgeNode.graph_id == graph_id, KnowledgeNode.deleted_at.is_(None))
            .order_by(KnowledgeNode.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_active(self, node_id: str) -> KnowledgeNode | None:
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.id == node_id,
            KnowledgeNode.deleted_at.is_(None),
        )
        return self.db.scalars(stmt).first()

    def add(self, node: KnowledgeNode) -> KnowledgeNode:
        self.db.add(node)
        self.db.flush()
        return node

    def soft_delete(self, node: KnowledgeNode) -> None:
        node.deleted_at = datetime.now(UTC)
        self.db.flush()

    def soft_delete_by_graph(self, graph_id: str) -> None:
        now = datetime.now(UTC)
        for node in self.list_active_by_graph(graph_id):
            node.deleted_at = now
        self.db.flush()
