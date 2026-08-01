from app.schemas.common import APIModel, EdgeType, TimestampRead


class EdgeCreate(APIModel):
    source_node_id: str
    target_node_id: str
    type: EdgeType
    custom_label: str | None = None


class EdgeUpdate(APIModel):
    type: EdgeType | None = None
    custom_label: str | None = None
    reverse: bool = False


class EdgeRead(TimestampRead):
    id: str
    graph_id: str
    source_node_id: str
    target_node_id: str
    type: EdgeType
    custom_label: str | None = None
