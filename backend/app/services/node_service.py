from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models.node import KnowledgeNode
from app.repositories.edge_repo import EdgeRepository
from app.repositories.graph_repo import GraphRepository
from app.repositories.node_repo import NodeRepository
from app.repositories.summary_repo import SummaryRepository
from app.schemas.node import NodeCreate, NodePositionUpdate, NodeRead, NodeUpdate
from app.services.cascade import soft_delete_node_content


class NodeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.graphs = GraphRepository(db)
        self.nodes = NodeRepository(db)
        self.edges = EdgeRepository(db)
        self.summaries = SummaryRepository(db)

    def _require_graph(self, graph_id: str) -> None:
        if not self.graphs.get_active(graph_id):
            raise NotFoundError("GRAPH_NOT_FOUND", f"Graph {graph_id} not found")

    def _to_read(self, node: KnowledgeNode) -> NodeRead:
        preview = None
        if node.current_summary_version_id:
            version = self.summaries.get_active(node.current_summary_version_id)
            if version:
                preview = version.content
        return NodeRead(
            id=node.id,
            graph_id=node.graph_id,
            title=node.title,
            node_type=node.node_type,
            position_x=node.position_x,
            position_y=node.position_y,
            current_summary_version_id=node.current_summary_version_id,
            summary_preview=preview,
            created_at=node.created_at,
            updated_at=node.updated_at,
        )

    def list_nodes(self, graph_id: str) -> list[NodeRead]:
        self._require_graph(graph_id)
        return [self._to_read(node) for node in self.nodes.list_active_by_graph(graph_id)]

    def get_node(self, node_id: str) -> NodeRead:
        node = self.nodes.get_active(node_id)
        if not node:
            raise NotFoundError("NODE_NOT_FOUND", f"Node {node_id} not found")
        return self._to_read(node)

    def create_node(self, graph_id: str, payload: NodeCreate) -> NodeRead:
        self._require_graph(graph_id)
        node = KnowledgeNode(
            id=str(uuid4()),
            graph_id=graph_id,
            title=payload.title.strip(),
            node_type=payload.node_type.value,
            position_x=payload.position_x,
            position_y=payload.position_y,
        )
        self.nodes.add(node)
        self.db.commit()
        self.db.refresh(node)
        return self._to_read(node)

    def update_node(self, node_id: str, payload: NodeUpdate) -> NodeRead:
        node = self.nodes.get_active(node_id)
        if not node:
            raise NotFoundError("NODE_NOT_FOUND", f"Node {node_id} not found")
        if payload.title is not None:
            node.title = payload.title.strip()
        if payload.node_type is not None:
            node.node_type = payload.node_type.value
        self.db.commit()
        self.db.refresh(node)
        return self._to_read(node)

    def update_position(self, node_id: str, payload: NodePositionUpdate) -> NodeRead:
        node = self.nodes.get_active(node_id)
        if not node:
            raise NotFoundError("NODE_NOT_FOUND", f"Node {node_id} not found")
        node.position_x = payload.x
        node.position_y = payload.y
        self.db.commit()
        self.db.refresh(node)
        return self._to_read(node)

    def delete_node(self, node_id: str) -> None:
        node = self.nodes.get_active(node_id)
        if not node:
            raise NotFoundError("NODE_NOT_FOUND", f"Node {node_id} not found")
        if self.edges.count_active_for_node(node_id) > 0:
            raise ConflictError(
                "NODE_HAS_EDGES",
                "Cannot delete a node that still has edges. Remove connected edges first.",
            )
        soft_delete_node_content(self.db, node_id)
        node.current_summary_version_id = None
        self.nodes.soft_delete(node)
        self.db.commit()
