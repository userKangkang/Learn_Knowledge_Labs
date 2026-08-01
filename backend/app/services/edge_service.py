from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import AppError, ConflictError, NotFoundError
from app.models.edge import KnowledgeEdge
from app.repositories.edge_repo import EdgeRepository
from app.repositories.graph_repo import GraphRepository
from app.repositories.node_repo import NodeRepository
from app.schemas.common import EdgeType
from app.schemas.edge import EdgeCreate, EdgeUpdate


class EdgeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.graphs = GraphRepository(db)
        self.nodes = NodeRepository(db)
        self.edges = EdgeRepository(db)

    def _require_graph(self, graph_id: str) -> None:
        if not self.graphs.get_active(graph_id):
            raise NotFoundError("GRAPH_NOT_FOUND", f"Graph {graph_id} not found")

    def _validate_endpoints(self, graph_id: str, source_node_id: str, target_node_id: str) -> None:
        if source_node_id == target_node_id:
            raise AppError("SELF_LOOP_FORBIDDEN", "Self-loop edges are not allowed", status_code=400)

        source = self.nodes.get_active(source_node_id)
        target = self.nodes.get_active(target_node_id)
        if not source or source.graph_id != graph_id:
            raise NotFoundError("SOURCE_NODE_NOT_FOUND", f"Source node {source_node_id} not found in graph")
        if not target or target.graph_id != graph_id:
            raise NotFoundError("TARGET_NODE_NOT_FOUND", f"Target node {target_node_id} not found in graph")

    def _validate_custom_label(self, edge_type: EdgeType, custom_label: str | None) -> str | None:
        if edge_type == EdgeType.CUSTOM:
            label = (custom_label or "").strip()
            if not label:
                raise AppError("CUSTOM_LABEL_REQUIRED", "CUSTOM edges require custom_label", status_code=400)
            return label
        return custom_label

    def list_edges(self, graph_id: str) -> list[KnowledgeEdge]:
        self._require_graph(graph_id)
        return self.edges.list_active_by_graph(graph_id)

    def get_edge(self, edge_id: str) -> KnowledgeEdge:
        edge = self.edges.get_active(edge_id)
        if not edge:
            raise NotFoundError("EDGE_NOT_FOUND", f"Edge {edge_id} not found")
        return edge

    def create_edge(self, graph_id: str, payload: EdgeCreate) -> KnowledgeEdge:
        self._require_graph(graph_id)
        self._validate_endpoints(graph_id, payload.source_node_id, payload.target_node_id)
        custom_label = self._validate_custom_label(payload.type, payload.custom_label)

        duplicate = self.edges.find_active_duplicate(
            graph_id=graph_id,
            source_node_id=payload.source_node_id,
            target_node_id=payload.target_node_id,
            edge_type=payload.type.value,
        )
        if duplicate:
            raise ConflictError("DUPLICATE_EDGE", "An active edge with the same type already exists between these nodes")

        edge = KnowledgeEdge(
            id=str(uuid4()),
            graph_id=graph_id,
            source_node_id=payload.source_node_id,
            target_node_id=payload.target_node_id,
            type=payload.type.value,
            custom_label=custom_label,
        )
        self.edges.add(edge)
        self.db.commit()
        self.db.refresh(edge)
        return edge

    def update_edge(self, edge_id: str, payload: EdgeUpdate) -> KnowledgeEdge:
        edge = self.get_edge(edge_id)
        next_type = payload.type if payload.type is not None else EdgeType(edge.type)
        next_label = payload.custom_label if payload.custom_label is not None else edge.custom_label
        next_label = self._validate_custom_label(next_type, next_label)

        next_source = edge.target_node_id if payload.reverse else edge.source_node_id
        next_target = edge.source_node_id if payload.reverse else edge.target_node_id
        if payload.reverse:
            self._validate_endpoints(edge.graph_id, next_source, next_target)

        duplicate = self.edges.find_active_duplicate(
            graph_id=edge.graph_id,
            source_node_id=next_source,
            target_node_id=next_target,
            edge_type=next_type.value,
            exclude_edge_id=edge.id,
        )
        if duplicate:
            raise ConflictError(
                "DUPLICATE_EDGE",
                "An active edge with the same type already exists between these nodes",
            )

        edge.source_node_id = next_source
        edge.target_node_id = next_target
        edge.type = next_type.value
        edge.custom_label = next_label
        self.db.commit()
        self.db.refresh(edge)
        return edge

    def delete_edge(self, edge_id: str) -> None:
        edge = self.get_edge(edge_id)
        self.edges.soft_delete(edge)
        self.db.commit()
