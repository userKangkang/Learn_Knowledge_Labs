from app.schemas.common import APIModel, NodeType, TimestampRead


class NodeCreate(APIModel):
    title: str
    node_type: NodeType = NodeType.CONCEPT
    position_x: float = 0.0
    position_y: float = 0.0


class NodeUpdate(APIModel):
    title: str | None = None
    node_type: NodeType | None = None


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
