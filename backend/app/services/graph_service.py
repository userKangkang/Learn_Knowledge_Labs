from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models.graph import KnowledgeGraph
from app.repositories.edge_repo import EdgeRepository
from app.repositories.graph_repo import GraphRepository
from app.repositories.node_repo import NodeRepository
from app.schemas.graph import GraphCreate, GraphUpdate
from app.services.cascade import soft_delete_graph_content


class GraphService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.graphs = GraphRepository(db)
        self.nodes = NodeRepository(db)
        self.edges = EdgeRepository(db)

    def list_graphs(self) -> list[KnowledgeGraph]:
        return self.graphs.list_active()

    def get_graph(self, graph_id: str) -> KnowledgeGraph:
        graph = self.graphs.get_active(graph_id)
        if not graph:
            raise NotFoundError("GRAPH_NOT_FOUND", f"Graph {graph_id} not found")
        return graph

    def create_graph(self, payload: GraphCreate) -> KnowledgeGraph:
        graph = KnowledgeGraph(
            id=str(uuid4()),
            title=payload.title.strip(),
            description=payload.description,
        )
        self.graphs.add(graph)
        self.db.commit()
        self.db.refresh(graph)
        return graph

    def update_graph(self, graph_id: str, payload: GraphUpdate) -> KnowledgeGraph:
        graph = self.get_graph(graph_id)
        if payload.title is not None:
            graph.title = payload.title.strip()
        if payload.description is not None:
            graph.description = payload.description
        self.db.commit()
        self.db.refresh(graph)
        return graph

    def delete_graph(self, graph_id: str) -> None:
        graph = self.get_graph(graph_id)
        # Cascade soft-delete: sessions/messages/summaries, then edges, nodes, graph
        soft_delete_graph_content(self.db, graph_id)
        self.edges.soft_delete_by_graph(graph_id)
        for node in self.nodes.list_active_by_graph(graph_id):
            node.current_summary_version_id = None
        self.nodes.soft_delete_by_graph(graph_id)
        self.graphs.soft_delete(graph)
        self.db.commit()
