"""Concept-map workflow: landscape, candidate review, and final minimal explanation graph."""

import json
from uuid import uuid4

from sqlalchemy import select

from app.errors import AppError, NotFoundError
from app.models.node import KnowledgeNode
from app.models.paper_study import (
    KnowledgeNodePaperReference,
    PaperConceptItem,
    PaperConceptMap,
    PaperConceptRelation,
    PaperProblemCard,
    PaperStudy,
)
from app.schemas.paper_study import (
    AttachConceptNode,
    PaperConceptFinalize,
    PaperConceptItemRead,
    PaperConceptItemUpdate,
    PaperConceptMapRead,
    PaperConceptRelationRead,
)
from app.services.paper_study.base import PaperStudyServiceBase
from app.services.paper_study.helpers import clean_json
from app.services.paper_study.prompts import (
    CONCEPT_CANDIDATE_PROMPT,
    CONCEPT_FINAL_PROMPT,
    CONCEPT_LANDSCAPE_PROMPT,
)


class PaperConceptMapService(PaperStudyServiceBase):
    def _map_read(self, concept_map: PaperConceptMap) -> PaperConceptMapRead:
        def read_list(value: object) -> list:
            if isinstance(value, str):
                try:
                    value = json.loads(value or "[]")
                except json.JSONDecodeError:
                    return []
            return value if isinstance(value, list) else []

        return PaperConceptMapRead(
            id=concept_map.id, problem_card_id=concept_map.problem_card_id,
            workflow_stage=concept_map.workflow_stage,
            landscape_items=read_list(concept_map.landscape_json),
            candidate_review=read_list(concept_map.candidate_review_json),
            confirmed_candidate_keys=read_list(concept_map.confirmed_candidate_keys_json),
            items=[PaperConceptItemRead.model_validate(item) for item in self.repo.list_concept_items(concept_map.id)],
            relations=[PaperConceptRelationRead.model_validate(item) for item in self.repo.list_relations(concept_map.id)],
        )

    def get_concept_map(self, card_id: str) -> PaperConceptMapRead | None:
        if not self.repo.get_card(card_id):
            raise NotFoundError("PAPER_PROBLEM_NOT_FOUND", "问题卡不存在")
        return self._map_read(item) if (item := self.repo.get_concept_map(card_id)) else None

    def _concept_source(self, card: PaperProblemCard, study: PaperStudy, extra: dict[str, object] | None = None) -> dict[str, object]:
        document = self._require_paper_material(study)
        source: dict[str, object] = {"problem_card": self._card_read(card).model_dump(mode="json")}
        if (document.extracted_text or "").strip():
            source["primary_paper_text"] = document.extracted_text
        if (document.kimi_detailed_analysis or "").strip():
            source["secondary_kimi_detailed_reading"] = document.kimi_detailed_analysis
        if extra:
            source.update(extra)
        return source

    def _replace_concept_map(self, card_id: str) -> PaperConceptMap:
        existing = self.repo.get_concept_map(card_id)
        if existing:
            self.db.delete(existing)
            self.db.flush()
        concept_map = PaperConceptMap(id=str(uuid4()), problem_card_id=card_id)
        self.repo.add(concept_map)
        return concept_map

    def generate_concept_map(self, card_id: str, text_model: str | None = None) -> PaperConceptMapRead:
        card = self.repo.get_card(card_id)
        if not card:
            raise NotFoundError("PAPER_PROBLEM_NOT_FOUND", "问题卡不存在")
        study = self._require_study(card.study_id)
        provider, model = self._text_route(text_model)
        raw = self._collect(
            provider=provider, model=model, system=CONCEPT_LANDSCAPE_PROMPT,
            messages=[{"role": "user", "content": json.dumps(self._concept_source(card, study), ensure_ascii=False)}],
        )
        items = clean_json(raw).get("items")
        if not isinstance(items, list) or not items:
            raise AppError("LLM_JSON_INVALID", "模型没有返回知识点分类", status_code=502)
        allowed = {"MECHANISM", "COMPONENT", "PHENOMENON", "EVIDENCE"}
        items = [
            item for item in items[:24]
            if isinstance(item, dict) and str(item.get("type") or "").upper() in allowed and str(item.get("key") or "").strip()
        ]
        if not items:
            raise AppError("LLM_JSON_INVALID", "模型没有返回可审核的知识点分类", status_code=502)
        concept_map = self._replace_concept_map(card.id)
        concept_map.workflow_stage = "LANDSCAPE"
        concept_map.landscape_json = items
        card.selected = True
        card.status = "EXPLORING"
        study.status = "EXPLORING"
        self.db.commit()
        return self._map_read(concept_map)

    def review_concept_candidates(self, card_id: str, text_model: str | None = None) -> PaperConceptMapRead:
        card = self.repo.get_card(card_id)
        if not card:
            raise NotFoundError("PAPER_PROBLEM_NOT_FOUND", "问题卡不存在")
        study = self._require_study(card.study_id)
        concept_map = self.repo.get_concept_map(card.id)
        if not concept_map or concept_map.workflow_stage != "LANDSCAPE":
            raise AppError("CONCEPT_STAGE_INVALID", "请先完成知识点分类并确认后再审核准入", status_code=400)
        landscape = concept_map.landscape_json or []
        provider, model = self._text_route(text_model)
        raw = self._collect(
            provider=provider, model=model, system=CONCEPT_CANDIDATE_PROMPT,
            messages=[{"role": "user", "content": json.dumps(self._concept_source(card, study, {"knowledge_landscape": landscape}), ensure_ascii=False)}],
        )
        candidates = clean_json(raw).get("items")
        if not isinstance(candidates, list):
            raise AppError("LLM_JSON_INVALID", "模型没有返回知识导图准入审核", status_code=502)
        reviewed_by_key = {str(item.get("key")): item for item in candidates[:32] if isinstance(item, dict) and str(item.get("key") or "").strip()}
        complete_review: list[dict] = []
        for landscape_item in landscape[:24]:
            if not isinstance(landscape_item, dict):
                continue
            key = str(landscape_item.get("key") or "").strip()
            if not key:
                continue
            item_type = str(landscape_item.get("type") or "").upper()
            reviewed = dict(reviewed_by_key.get(key) or {})
            reviewed["key"] = key
            reviewed["title"] = str(reviewed.get("title") or landscape_item.get("title") or key)
            reviewed["type"] = item_type
            reviewed["paper_anchor"] = str(reviewed.get("paper_anchor") or landscape_item.get("paper_anchor") or "")
            eligible = item_type in {"MECHANISM", "COMPONENT"}
            reviewed["eligible"] = eligible
            reviewed["graph_candidate"] = bool(reviewed.get("graph_candidate")) if eligible else False
            if not reviewed.get("reason"):
                reviewed["reason"] = "可作为通用机制/组件候选，请由你决定是否纳入。" if eligible else "这是问题现象或论文证据，本轮不作为知识导图候选。"
            reviewed.setdefault("reusable_beyond_paper", "")
            reviewed.setdefault("causal_explanation_need", "")
            complete_review.append(reviewed)
        candidates = complete_review
        concept_map.candidate_review_json = candidates
        concept_map.workflow_stage = "REVIEW"
        self.db.commit()
        return self._map_read(concept_map)

    def finalize_concept_map(self, card_id: str, payload: PaperConceptFinalize) -> PaperConceptMapRead:
        card = self.repo.get_card(card_id)
        if not card:
            raise NotFoundError("PAPER_PROBLEM_NOT_FOUND", "问题卡不存在")
        study = self._require_study(card.study_id)
        concept_map = self.repo.get_concept_map(card.id)
        if not concept_map or concept_map.workflow_stage != "REVIEW":
            raise AppError("CONCEPT_STAGE_INVALID", "请先完成候选准入审核并确认后再生成重要程度", status_code=400)
        landscape = concept_map.landscape_json or []
        candidates = concept_map.candidate_review_json or []
        eligible_keys = {
            str(item.get("key"))
            for item in candidates
            if isinstance(item, dict) and item.get("eligible") is True and str(item.get("type") or "").upper() in {"MECHANISM", "COMPONENT"}
        }
        confirmed = [str(key) for key in payload.confirmed_candidate_keys if str(key) in eligible_keys]
        if not confirmed:
            raise AppError("CONCEPT_CANDIDATES_REQUIRED", "请至少确认一个基础机制或系统组件后再生成重要程度", status_code=400)
        source = self._concept_source(card, study, {"knowledge_landscape": landscape, "candidate_review": candidates, "confirmed_candidate_keys": confirmed})
        provider, model = self._text_route(payload.text_model)
        raw = self._collect(
            provider=provider, model=model, system=CONCEPT_FINAL_PROMPT,
            messages=[{"role": "user", "content": json.dumps(source, ensure_ascii=False)}],
        )
        result = clean_json(raw)
        items = result.get("items")
        if not isinstance(items, list) or not items:
            raise AppError("LLM_JSON_INVALID", "模型没有返回最小解释图", status_code=502)
        self.db.delete(concept_map)
        self.db.flush()
        concept_map = PaperConceptMap(
            id=str(uuid4()), problem_card_id=card.id, workflow_stage="COMPLETED",
            landscape_json=landscape,
            candidate_review_json=candidates,
            confirmed_candidate_keys_json=confirmed,
        )
        self.repo.add(concept_map)
        by_key: dict[str, str] = {}
        for index, data in enumerate(items[:14]):
            if not isinstance(data, dict):
                continue
            category = str(data.get("category") or "").upper()
            if category not in {"MUST", "ON_DEMAND", "EXTENSION"}:
                continue
            key = str(data.get("key") or f"item-{index}")
            item = PaperConceptItem(
                id=str(uuid4()), concept_map_id=concept_map.id, title=str(data.get("title") or key).strip(),
                explanation=str(data.get("explanation") or "").strip(), category=category,
                paper_anchor=str(data.get("paper_anchor") or "").strip(), order_index=index,
            )
            self.repo.add(item)
            by_key[key] = item.id
        for relation in result.get("relations") or []:
            if not isinstance(relation, dict):
                continue
            source_id, target_id = by_key.get(str(relation.get("source_key"))), by_key.get(str(relation.get("target_key")))
            if source_id and target_id and source_id != target_id:
                self.repo.add(PaperConceptRelation(
                    id=str(uuid4()), concept_map_id=concept_map.id, source_item_id=source_id,
                    target_item_id=target_id, relation_label=str(relation.get("relation_label") or "相关"),
                ))
        if not by_key:
            raise AppError("LLM_JSON_INVALID", "模型没有返回可用的最小解释图节点", status_code=502)
        card.selected = True
        card.status = "EXPLORING"
        study.status = "EXPLORING"
        self.db.commit()
        return self._map_read(concept_map)

    def update_concept_item(self, item_id: str, payload: PaperConceptItemUpdate) -> PaperConceptItemRead:
        item = self.repo.get_concept_item(item_id)
        if not item:
            raise NotFoundError("PAPER_CONCEPT_NOT_FOUND", "解释图节点不存在")
        if payload.user_status is not None:
            item.user_status = payload.user_status
        self.db.commit()
        self.db.refresh(item)
        return PaperConceptItemRead.model_validate(item)

    def attach_concept_node(self, item_id: str, payload: AttachConceptNode) -> PaperConceptItemRead:
        item = self.repo.get_concept_item(item_id)
        if not item:
            raise NotFoundError("PAPER_CONCEPT_NOT_FOUND", "解释图节点不存在")
        concept_map = self.db.get(PaperConceptMap, item.concept_map_id)
        if concept_map is None:
            raise NotFoundError("PAPER_CONCEPT_MAP_NOT_FOUND", "解释图记录不存在")
        card = self.repo.get_card(concept_map.problem_card_id)
        if card is None:
            raise NotFoundError("PAPER_PROBLEM_NOT_FOUND", "问题卡不存在")
        study = self._require_study(card.study_id)
        node = self.nodes.get_active(payload.existing_node_id) if payload.existing_node_id else None
        if node and node.graph_id != study.graph_id:
            raise AppError("NODE_GRAPH_MISMATCH", "只能关联当前知识图的节点", status_code=400)
        if not node and payload.create_node:
            position_x, position_y = payload.position_x, payload.position_y
            if position_x == 0 and position_y == 0:
                graph_nodes = self.nodes.list_active_by_graph(study.graph_id)
                if graph_nodes:
                    position_x = max(existing.position_x for existing in graph_nodes) + 280
                    position_y = graph_nodes[-1].position_y
                else:
                    position_x, position_y = 120, 120
            node = KnowledgeNode(
                id=str(uuid4()), graph_id=study.graph_id, title=item.title,
                node_type="CONCEPT", position_x=position_x, position_y=position_y,
            )
            self.nodes.add(node)
        if not node:
            raise AppError("NODE_REQUIRED", "请选择已有节点或明确创建节点", status_code=400)
        document = self.repo.get_document(study.id)
        if document is None:
            raise NotFoundError("PAPER_DOCUMENT_NOT_FOUND", "论文文档不存在")
        item.graph_node_id = node.id
        location = payload.location.strip() or item.paper_anchor
        reference = self.db.scalar(
            select(KnowledgeNodePaperReference).where(
                KnowledgeNodePaperReference.node_id == node.id,
                KnowledgeNodePaperReference.document_id == document.id,
            )
        )
        if reference:
            reference.location = location
            reference.link_type = payload.link_type
            reference.note = payload.note.strip()
        else:
            self.repo.add(KnowledgeNodePaperReference(
                id=str(uuid4()), node_id=node.id, document_id=document.id,
                location=location, link_type=payload.link_type, note=payload.note.strip(),
            ))
        self.db.commit()
        self.db.refresh(item)
        return PaperConceptItemRead.model_validate(item)
