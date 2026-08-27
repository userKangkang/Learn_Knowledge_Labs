"""Temporary, isolated knowledge-point conversations from the paper overview."""

import json
from collections.abc import Iterator
from uuid import uuid4

from app.errors import AppError, ConflictError, NotFoundError
from app.models.node import KnowledgeNode
from app.models.paper_study import KnowledgeNodePaperReference, PaperKnowledgeInquiry, PaperKnowledgeInquiryMessage
from app.models.summary import NodeSummaryVersion
from app.schemas.paper_study import (
    PaperKnowledgeCardSave,
    PaperKnowledgeCardSaveRead,
    PaperKnowledgeInquiryCreate,
    PaperKnowledgeInquiryMessageCreate,
    PaperKnowledgeInquiryRead,
)
from app.services.node_service import NodeService
from app.services.paper_study.base import PaperStudyServiceBase
from app.services.paper_study.prompts import KNOWLEDGE_INQUIRY_PROMPT
from app.services.sse import sse_event


class PaperKnowledgeInquiryService(PaperStudyServiceBase):
    def create_inquiry(self, study_id: str, payload: PaperKnowledgeInquiryCreate) -> PaperKnowledgeInquiryRead:
        study = self._require_study(study_id)
        self._require_paper_material(study)
        title = payload.title.strip()
        if not title:
            raise AppError("KNOWLEDGE_INQUIRY_TITLE_EMPTY", "知识点名称不能为空", status_code=400)
        inquiry = self.repo.add(PaperKnowledgeInquiry(id=str(uuid4()), study_id=study.id, title=title))
        self.db.commit()
        self.db.refresh(inquiry)
        return self._knowledge_inquiry_read(inquiry)

    def get_inquiry(self, study_id: str, inquiry_id: str) -> PaperKnowledgeInquiryRead:
        return self._knowledge_inquiry_read(self._require_inquiry(study_id, inquiry_id))

    def _require_inquiry(self, study_id: str, inquiry_id: str) -> PaperKnowledgeInquiry:
        self._require_study(study_id)
        inquiry = self.repo.get_knowledge_inquiry(inquiry_id)
        if not inquiry or inquiry.study_id != study_id:
            raise NotFoundError("KNOWLEDGE_INQUIRY_NOT_FOUND", "临时知识点对话不存在")
        return inquiry

    def _context(self, study, inquiry: PaperKnowledgeInquiry) -> list[dict]:
        document = self._require_paper_material(study)
        context: dict[str, object] = {
            "knowledge_point": inquiry.title,
            "instruction": "只回答这个知识点，不要把临时对话内容写回论文全貌主对话。",
        }
        if (document.extracted_text or "").strip():
            context["primary_paper_text"] = document.extracted_text
            context["primary_paper_text_note"] = "这是从用户 PDF 提取的原文文本，是事实判断的优先依据。"
        if (document.kimi_detailed_analysis or "").strip():
            context["secondary_kimi_detailed_reading"] = document.kimi_detailed_analysis
            context["secondary_kimi_note"] = "这是辅助解读，不得覆盖或替代原文；若冲突，以原文为准。"
        messages: list[dict] = [{"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
        messages.extend(
            {"role": item.role.lower(), "content": item.content}
            for item in self.repo.list_knowledge_inquiry_messages(inquiry.id)
        )
        return messages

    def _add_message(self, inquiry_id: str, role: str, content: str) -> PaperKnowledgeInquiryMessage:
        return self.repo.add(PaperKnowledgeInquiryMessage(
            id=str(uuid4()),
            inquiry_id=inquiry_id,
            role=role,
            content=content.strip(),
            sequence_index=self.repo.next_knowledge_inquiry_message_index(inquiry_id),
        ))

    def stream_message(
        self,
        study_id: str,
        inquiry_id: str,
        payload: PaperKnowledgeInquiryMessageCreate,
    ) -> Iterator[str]:
        full_text = ""
        try:
            study = self._require_study(study_id)
            inquiry = self._require_inquiry(study_id, inquiry_id)
            if inquiry.status != "ACTIVE":
                raise ConflictError("KNOWLEDGE_INQUIRY_CLOSED", "这段临时知识点对话已经结束")
            content = payload.content.strip()
            if not content:
                raise AppError("MESSAGE_EMPTY", "问题不能为空", status_code=400)
            self._add_message(inquiry.id, "USER", content)
            self.db.commit()
            provider, model = self._text_route(payload.text_model)
            for chunk in self.gateway.stream(
                provider=provider,
                model=model,
                system_prompt=KNOWLEDGE_INQUIRY_PROMPT,
                messages=self._context(study, inquiry),
                web_search=False,
            ):
                if chunk.status_text:
                    yield sse_event("status", {"message": chunk.status_text})
                if chunk.content_delta:
                    full_text += chunk.content_delta
                    yield sse_event("delta", {"delta": chunk.content_delta})
            if not full_text.strip():
                raise AppError("LLM_EMPTY_RESPONSE", "模型返回空内容", status_code=502)
            self._add_message(inquiry.id, "ASSISTANT", full_text)
            self.db.commit()
            yield sse_event("completed", {"content": full_text, "inquiry_id": inquiry.id})
        except AppError as error:
            yield sse_event("failed", {"error_code": error.code, "error_message": error.message})
        except Exception as error:  # noqa: BLE001
            yield sse_event("failed", {"error_code": "KNOWLEDGE_INQUIRY_UNEXPECTED_ERROR", "error_message": str(error)})

    def save_card(
        self,
        study_id: str,
        inquiry_id: str,
        payload: PaperKnowledgeCardSave,
    ) -> PaperKnowledgeCardSaveRead:
        study = self._require_study(study_id)
        inquiry = self._require_inquiry(study_id, inquiry_id)
        if inquiry.status == "SAVED" and inquiry.graph_node_id:
            node = NodeService(self.db).get_node(inquiry.graph_node_id)
            return PaperKnowledgeCardSaveRead(inquiry=self._knowledge_inquiry_read(inquiry), node=node)
        if inquiry.status != "ACTIVE":
            raise ConflictError("KNOWLEDGE_INQUIRY_CLOSED", "这段临时知识点对话已经结束")
        document = self._require_paper_material(study)
        if not any(message.role == "ASSISTANT" and message.content.strip() for message in self.repo.list_knowledge_inquiry_messages(inquiry.id)):
            raise AppError("KNOWLEDGE_INQUIRY_EMPTY", "请先完成一次临时知识点对话，再保存知识卡片", status_code=400)
        title = payload.title.strip()
        if not title:
            raise AppError("KNOWLEDGE_CARD_TITLE_EMPTY", "知识点名称不能为空", status_code=400)

        existing_nodes = self.nodes.list_active_by_graph(study.graph_id)
        position_x = max((node.position_x for node in existing_nodes), default=-300.0) + 420.0
        position_y = 120.0
        node = self.nodes.add(KnowledgeNode(
            id=str(uuid4()),
            graph_id=study.graph_id,
            title=title,
            node_type="CONCEPT",
            position_x=position_x,
            position_y=position_y,
            understanding_level="NEEDS_WORK",
        ))
        summary = payload.summary.strip()
        if summary:
            version = NodeSummaryVersion(
                id=str(uuid4()),
                node_id=node.id,
                version_number=1,
                content=summary,
                author_type="USER",
                generated_from_message_ids="[]",
            )
            self.db.add(version)
            self.db.flush()
            node.current_summary_version_id = version.id
        self.db.add(KnowledgeNodePaperReference(
            id=str(uuid4()),
            node_id=node.id,
            document_id=document.id,
            location=f"论文全貌·临时知识点：{title}",
            link_type="MECHANISM",
            note="由临时知识点对话保存",
        ))
        inquiry.status = "SAVED"
        inquiry.graph_node_id = node.id
        self.db.commit()
        self.db.refresh(inquiry)
        return PaperKnowledgeCardSaveRead(
            inquiry=self._knowledge_inquiry_read(inquiry),
            node=NodeService(self.db).get_node(node.id),
        )

    def discard(self, study_id: str, inquiry_id: str) -> None:
        inquiry = self._require_inquiry(study_id, inquiry_id)
        if inquiry.status == "SAVED":
            raise ConflictError("KNOWLEDGE_INQUIRY_SAVED", "已保存为知识节点，不能丢弃")
        inquiry.status = "DISCARDED"
        self.db.commit()
