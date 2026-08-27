"""Shared base for paper-study services: dependencies and read-model helpers."""

import json
from collections.abc import Iterator

from app.config import get_settings
from app.errors import AppError, NotFoundError
from app.models.paper_study import (
    PaperProblemCard,
    PaperStudy,
    PaperStudyDocument,
    PaperStudyMessage,
    PaperStudyOverview,
    PaperKnowledgeInquiry,
    PaperKnowledgeInquiryMessage,
)
from app.repositories.graph_repo import GraphRepository
from app.repositories.node_repo import NodeRepository
from app.repositories.paper_study_repo import PaperStudyRepository
from app.schemas.paper_study import (
    PaperDocumentRead,
    PaperOverviewRead,
    PaperProblemCardRead,
    PaperStudyMessageRead,
    PaperStudyRead,
    PaperKnowledgeInquiryRead,
    PaperKnowledgeInquiryMessageRead,
)
from app.services.llm_gateway import LLMGateway
from app.services.model_routing import resolve_text_route


class PaperStudyDeps:
    """Shared dependencies built once per request and reused by all sub-services."""

    def __init__(self, db) -> None:
        self.db = db
        self.repo = PaperStudyRepository(db)
        self.graphs = GraphRepository(db)
        self.nodes = NodeRepository(db)
        self.gateway = LLMGateway()
        self.settings = get_settings()


class PaperStudyServiceBase:
    """Common repository/gateway dependencies and shared read-model builders."""

    def __init__(self, db, deps: PaperStudyDeps | None = None) -> None:
        deps = deps or PaperStudyDeps(db)
        self.db = deps.db
        self.repo = deps.repo
        self.graphs = deps.graphs
        self.nodes = deps.nodes
        self.gateway = deps.gateway
        self.settings = deps.settings

    def _require_graph(self, graph_id: str) -> None:
        if not self.graphs.get_active(graph_id):
            raise NotFoundError("GRAPH_NOT_FOUND", "知识图不存在")

    def _require_study(self, study_id: str) -> PaperStudy:
        study = self.repo.get_study(study_id)
        if not study:
            raise NotFoundError("PAPER_STUDY_NOT_FOUND", "论文理解记录不存在")
        return study

    @staticmethod
    def _list(value: object) -> list[str]:
        if isinstance(value, str):
            try:
                value = json.loads(value or "[]")
            except json.JSONDecodeError:
                return []
        return [str(item) for item in value] if isinstance(value, list) else []

    def _document_read(self, item: PaperStudyDocument) -> PaperDocumentRead:
        return PaperDocumentRead(
            id=item.id, filename=item.filename, content_type=item.content_type, size_bytes=item.size_bytes,
            status=item.status, source_text_char_count=len(item.extracted_text or ""),
            kimi_detailed_analysis=item.kimi_detailed_analysis, error=item.error,
            created_at=item.created_at, updated_at=item.updated_at,
        )

    def _overview_read(self, item: PaperStudyOverview | None) -> PaperOverviewRead:
        return PaperOverviewRead.model_validate(item) if item else PaperOverviewRead()

    @staticmethod
    def _message_read(item: PaperStudyMessage) -> PaperStudyMessageRead:
        return PaperStudyMessageRead.model_validate(item)

    @staticmethod
    def _knowledge_inquiry_message_read(item: PaperKnowledgeInquiryMessage) -> PaperKnowledgeInquiryMessageRead:
        return PaperKnowledgeInquiryMessageRead.model_validate(item)

    def _knowledge_inquiry_read(self, item: PaperKnowledgeInquiry) -> PaperKnowledgeInquiryRead:
        return PaperKnowledgeInquiryRead(
            id=item.id,
            study_id=item.study_id,
            title=item.title,
            status=item.status,
            graph_node_id=item.graph_node_id,
            messages=[self._knowledge_inquiry_message_read(message) for message in self.repo.list_knowledge_inquiry_messages(item.id)],
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _card_read(self, item: PaperProblemCard) -> PaperProblemCardRead:
        return PaperProblemCardRead(
            id=item.id, study_id=item.study_id, title=item.title,
            qualitative_overview=item.qualitative_overview, technical_interpretation=item.technical_interpretation,
            paper_claims=self._list(item.paper_claims), paper_not_said=self._list(item.paper_not_said),
            user_interest=item.user_interest, user_stuck_point=item.user_stuck_point, selected=item.selected,
            status=item.status, verification_anchor=item.verification_anchor, verification_prompt=item.verification_prompt,
            verification_answer=item.verification_answer, verification_status=item.verification_status,
            order_index=item.order_index, created_at=item.created_at, updated_at=item.updated_at,
        )

    def _study_read(self, study: PaperStudy) -> PaperStudyRead:
        return PaperStudyRead(
            id=study.id, graph_id=study.graph_id, title=study.title, status=study.status,
            document=self._document_read(document) if (document := self.repo.get_document(study.id)) else None,
            overview=self._overview_read(self.repo.get_overview(study.id)),
            messages=[self._message_read(message) for message in self.repo.list_messages(study.id)],
            problem_cards=[self._card_read(card) for card in self.repo.list_cards(study.id)],
            created_at=study.created_at, updated_at=study.updated_at,
        )

    def _collect(self, *, provider: str, model: str, system: str, messages: list[dict]) -> str:
        content = ""
        for chunk in self.gateway.stream(provider=provider, model=model, system_prompt=system, messages=messages, web_search=False):
            content += chunk.content_delta or ""
        if not content.strip():
            raise AppError("LLM_EMPTY", "模型没有返回内容", status_code=502)
        return content

    def _text_route(self, text_model: str | None = None) -> tuple[str, str]:
        provider, model, _ = resolve_text_route(
            text_model=text_model,
            web_search=False,
            settings=self.settings,
        )
        return provider, model

    def _require_paper_material(self, study: PaperStudy) -> PaperStudyDocument:
        document = self.repo.get_document(study.id)
        if not document or not ((document.extracted_text or "").strip() or (document.kimi_detailed_analysis or "").strip()):
            raise AppError("PAPER_TEXT_REQUIRED", "请先提取可读的论文原文文本；若提取失败，可使用 Kimi 辅助详细解读", status_code=400)
        return document
