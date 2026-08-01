from app.schemas.common import APIModel, TimestampRead


class GraphCreate(APIModel):
    title: str
    description: str | None = None


class GraphUpdate(APIModel):
    title: str | None = None
    description: str | None = None


class GraphRead(TimestampRead):
    id: str
    title: str
    description: str | None = None
