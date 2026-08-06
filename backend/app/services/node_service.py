from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models.node import KnowledgeNode
from app.models.paper_study import KnowledgeNodePaperReference, PaperStudy, PaperStudyDocument
from app.repositories.edge_repo import EdgeRepository
from app.repositories.graph_repo import GraphRepository
from app.repositories.node_repo import NodeRepository
from app.repositories.summary_repo import SummaryRepository
from app.schemas.node import NodeCreate, NodePaperReferenceCreate, NodePaperReferenceRead, NodePositionUpdate, NodeRead, NodeUpdate
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

    def _to_read(
        self,
        node: KnowledgeNode,
        *,
        references: list[NodePaperReferenceRead] | None = None,
        summary_preview: str | None = None,
    ) -> NodeRead:
        if summary_preview is None and node.current_summary_version_id:
            version = self.summaries.get_active(node.current_summary_version_id)
            if version:
                summary_preview = version.content
        return NodeRead(
            id=node.id,
            graph_id=node.graph_id,
            title=node.title,
            node_type=node.node_type,
            position_x=node.position_x,
            position_y=node.position_y,
            current_summary_version_id=node.current_summary_version_id,
            summary_preview=summary_preview,
            understanding_level=node.understanding_level,
            paper_references=references if references is not None else self._paper_reference_reads(node.id),
            created_at=node.created_at,
            updated_at=node.updated_at,
        )

    @staticmethod
    def _paper_reference_read(
        reference: KnowledgeNodePaperReference,
        document: PaperStudyDocument,
        study: PaperStudy,
    ) -> NodePaperReferenceRead:
        return NodePaperReferenceRead(
            id=reference.id,
            document_id=document.id,
            study_id=study.id,
            study_title=study.title,
            filename=document.filename,
            location=reference.location,
            link_type=reference.link_type,
            note=reference.note,
            created_at=reference.created_at,
        )

    def _paper_reference_reads(self, node_id: str) -> list[NodePaperReferenceRead]:
        stmt = (
            select(KnowledgeNodePaperReference, PaperStudyDocument, PaperStudy)
            .join(PaperStudyDocument, PaperStudyDocument.id == KnowledgeNodePaperReference.document_id)
            .join(PaperStudy, PaperStudy.id == PaperStudyDocument.study_id)
            .where(KnowledgeNodePaperReference.node_id == node_id)
            .order_by(KnowledgeNodePaperReference.created_at.asc())
        )
        return [self._paper_reference_read(reference, document, study) for reference, document, study in self.db.execute(stmt).all()]

    def _paper_references_by_node_ids(self, node_ids: list[str]) -> dict[str, list[NodePaperReferenceRead]]:
        if not node_ids:
            return {}
        stmt = (
            select(KnowledgeNodePaperReference, PaperStudyDocument, PaperStudy)
            .join(PaperStudyDocument, PaperStudyDocument.id == KnowledgeNodePaperReference.document_id)
            .join(PaperStudy, PaperStudy.id == PaperStudyDocument.study_id)
            .where(KnowledgeNodePaperReference.node_id.in_(node_ids))
            .order_by(KnowledgeNodePaperReference.created_at.asc())
        )
        grouped: dict[str, list[NodePaperReferenceRead]] = {}
        for reference, document, study in self.db.execute(stmt).all():
            grouped.setdefault(reference.node_id, []).append(self._paper_reference_read(reference, document, study))
        return grouped

    def list_nodes(self, graph_id: str) -> list[NodeRead]:
        self._require_graph(graph_id)
        nodes = self.nodes.list_active_by_graph(graph_id)
        references_by_node = self._paper_references_by_node_ids([node.id for node in nodes])
        summary_ids = [node.current_summary_version_id for node in nodes if node.current_summary_version_id]
        summaries = {version.id: version for version in self.summaries.get_active_many(summary_ids)} if summary_ids else {}
        return [
            self._to_read(
                node,
                references=references_by_node.get(node.id, []),
                summary_preview=summaries[node.current_summary_version_id].content
                if node.current_summary_version_id in summaries
                else None,
            )
            for node in nodes
        ]

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
            understanding_level=payload.understanding_level,
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
        if payload.understanding_level is not None:
            node.understanding_level = payload.understanding_level
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

    def add_paper_reference(self, node_id: str, payload: NodePaperReferenceCreate) -> NodeRead:
        node = self.nodes.get_active(node_id)
        if not node:
            raise NotFoundError("NODE_NOT_FOUND", f"Node {node_id} not found")
        document = self.db.get(PaperStudyDocument, payload.document_id)
        if not document:
            raise NotFoundError("PAPER_DOCUMENT_NOT_FOUND", "论文文档不存在")
        study = self.db.get(PaperStudy, document.study_id)
        if not study or study.graph_id != node.graph_id:
            raise ConflictError("PAPER_GRAPH_MISMATCH", "只能关联当前知识图中的论文")
        reference = self.db.scalar(
            select(KnowledgeNodePaperReference).where(
                KnowledgeNodePaperReference.node_id == node.id,
                KnowledgeNodePaperReference.document_id == document.id,
            )
        )
        if reference:
            reference.location = payload.location.strip()
            reference.link_type = payload.link_type
            reference.note = payload.note.strip()
        else:
            self.db.add(KnowledgeNodePaperReference(
                id=str(uuid4()),
                node_id=node.id,
                document_id=document.id,
                location=payload.location.strip(),
                link_type=payload.link_type,
                note=payload.note.strip(),
            ))
        self.db.commit()
        self.db.refresh(node)
        return self._to_read(node)
