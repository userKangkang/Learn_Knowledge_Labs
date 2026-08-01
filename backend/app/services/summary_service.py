import json
from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import AppError, NotFoundError
from app.models.summary import NodeSummaryVersion
from app.repositories.node_repo import NodeRepository
from app.repositories.summary_repo import SummaryRepository
from app.schemas.common import AuthorType
from app.schemas.summary import SummaryCreate, SummaryUpdate, SummaryVersionRead


class SummaryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.nodes = NodeRepository(db)
        self.summaries = SummaryRepository(db)

    def _require_node(self, node_id: str):
        node = self.nodes.get_active(node_id)
        if not node:
            raise NotFoundError("NODE_NOT_FOUND", f"Node {node_id} not found")
        return node

    def _to_read(self, version: NodeSummaryVersion, current_id: str | None) -> SummaryVersionRead:
        try:
            message_ids = json.loads(version.generated_from_message_ids or "[]")
        except json.JSONDecodeError:
            message_ids = []
        return SummaryVersionRead(
            id=version.id,
            node_id=version.node_id,
            version_number=version.version_number,
            content=version.content,
            author_type=AuthorType(version.author_type),
            generated_from_message_ids=message_ids,
            created_at=version.created_at,
            is_current=version.id == current_id,
        )

    def get_current(self, node_id: str) -> SummaryVersionRead | None:
        node = self._require_node(node_id)
        if not node.current_summary_version_id:
            return None
        version = self.summaries.get_active(node.current_summary_version_id)
        if not version:
            return None
        return self._to_read(version, node.current_summary_version_id)

    def list_versions(self, node_id: str) -> list[SummaryVersionRead]:
        node = self._require_node(node_id)
        return [self._to_read(v, node.current_summary_version_id) for v in self.summaries.list_active_by_node(node_id)]

    def create_version(self, node_id: str, payload: SummaryCreate) -> SummaryVersionRead:
        node = self._require_node(node_id)
        content = payload.content.strip()
        if not content:
            raise AppError("SUMMARY_EMPTY", "Summary content cannot be empty", status_code=400)

        version = NodeSummaryVersion(
            id=str(uuid4()),
            node_id=node_id,
            version_number=self.summaries.next_version_number(node_id),
            content=content,
            author_type=AuthorType.USER.value,
            generated_from_message_ids="[]",
        )
        self.summaries.add(version)
        node.current_summary_version_id = version.id
        self.db.commit()
        self.db.refresh(version)
        return self._to_read(version, node.current_summary_version_id)

    def activate_version(self, node_id: str, version_id: str) -> SummaryVersionRead:
        node = self._require_node(node_id)
        version = self.summaries.get_active(version_id)
        if not version or version.node_id != node_id:
            raise NotFoundError("SUMMARY_NOT_FOUND", f"Summary version {version_id} not found")
        node.current_summary_version_id = version.id
        self.db.commit()
        return self._to_read(version, node.current_summary_version_id)

    def _require_version(self, node_id: str, version_id: str) -> tuple:
        node = self._require_node(node_id)
        version = self.summaries.get_active(version_id)
        if not version or version.node_id != node_id:
            raise NotFoundError("SUMMARY_NOT_FOUND", f"Summary version {version_id} not found")
        return node, version

    def update_version(self, node_id: str, version_id: str, payload: SummaryUpdate) -> SummaryVersionRead:
        node, version = self._require_version(node_id, version_id)
        content = payload.content.strip()
        if not content:
            raise AppError("SUMMARY_EMPTY", "Summary content cannot be empty", status_code=400)
        version.content = content
        self.db.commit()
        self.db.refresh(version)
        return self._to_read(version, node.current_summary_version_id)

    def delete_version(self, node_id: str, version_id: str) -> None:
        node, version = self._require_version(node_id, version_id)
        was_current = node.current_summary_version_id == version.id
        self.summaries.soft_delete(version)
        if was_current:
            remaining = self.summaries.list_active_by_node(node_id)
            node.current_summary_version_id = remaining[0].id if remaining else None
        self.db.commit()
