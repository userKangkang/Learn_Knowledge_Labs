from datetime import datetime
from typing import Literal

from app.schemas.common import APIModel, NodeType, TimestampRead


KnowledgeUnderstandingLevel = Literal["NEEDS_WORK", "BASIC", "DEEP"]
PaperReferenceType = Literal["PROBLEM_EVIDENCE", "MECHANISM", "RESULT", "BASELINE"]


class NodePaperReferenceRead(APIModel):
    id: str
    document_id: str
    study_id: str
    study_title: str
    filename: str
    location: str
    link_type: PaperReferenceType
    note: str
    created_at: datetime


class NodePaperReferenceCreate(APIModel):
    document_id: str
    location: str = ""
    link_type: PaperReferenceType = "MECHANISM"
    note: str = ""


class NodeCreate(APIModel):
    title: str
    node_type: NodeType = NodeType.CONCEPT
    position_x: float = 0.0
    position_y: float = 0.0
    understanding_level: KnowledgeUnderstandingLevel = "NEEDS_WORK"


class NodeUpdate(APIModel):
    title: str | None = None
    node_type: NodeType | None = None
    understanding_level: KnowledgeUnderstandingLevel | None = None


class NodePositionUpdate(APIModel):
    x: float
    y: float


class NodeRead(TimestampRead):
    id: str
    graph_id: str
    title: str
    node_type: NodeType
    position_x: float
    position_y: float
    current_summary_version_id: str | None = None
    summary_preview: str | None = None
    understanding_level: KnowledgeUnderstandingLevel = "NEEDS_WORK"
    paper_references: list[NodePaperReferenceRead] = []
