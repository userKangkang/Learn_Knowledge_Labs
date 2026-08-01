from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.graph import KnowledgeGraph


class GraphRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self) -> list[KnowledgeGraph]:
        stmt = (
            select(KnowledgeGraph)
            .where(KnowledgeGraph.deleted_at.is_(None))
            .order_by(KnowledgeGraph.updated_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_active(self, graph_id: str) -> KnowledgeGraph | None:
        stmt = select(KnowledgeGraph).where(
            KnowledgeGraph.id == graph_id,
            KnowledgeGraph.deleted_at.is_(None),
        )
        return self.db.scalars(stmt).first()

    def add(self, graph: KnowledgeGraph) -> KnowledgeGraph:
        self.db.add(graph)
        self.db.flush()
        return graph

    def soft_delete(self, graph: KnowledgeGraph) -> None:
        graph.deleted_at = datetime.now(UTC)
        self.db.flush()
