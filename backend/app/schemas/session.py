from app.schemas.common import APIModel, TimestampRead


class SessionCreate(APIModel):
    title: str | None = None


class SessionUpdate(APIModel):
    title: str | None = None


class SessionRead(TimestampRead):
    id: str
    node_id: str
    title: str
