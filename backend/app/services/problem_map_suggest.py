"""LLM-suggested shared problems and card links, applied only after user review."""

import json
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError, ConflictError, NotFoundError
from app.models.paper_study import PaperProblemCard
from app.models.problem_map import ProblemCardLink, SharedProblem, SharedProblemEdge
from app.repositories.graph_repo import GraphRepository
from app.repositories.paper_study_repo import PaperStudyRepository
from app.repositories.problem_map_repo import ProblemMapRepository
from app.schemas.problem_map import (
    ProblemMapApplyCardLink,
    ProblemMapApplyEdge,
    ProblemMapApplyProblem,
    ProblemMapApplyRequest,
    ProblemMapApplyResult,
    ProblemLinkType,
    ProblemMapSuggestionCardLink,
    ProblemMapSuggestionEdge,
    ProblemMapSuggestionProblem,
    ProblemMapSuggestResponse,
)
from app.services.llm_gateway import LLMGateway
from app.services.model_routing import resolve_text_route
from app.services.paper_study.helpers import clean_json
from app.services.problem_map_prompts import PROBLEM_MAP_SUGGEST_PROMPT

DEFAULT_RELATION_LABEL = "SPECIALIZES_INTO"
MAX_PROBLEMS = 24
MAX_EDGES = 40
MAX_CARD_LINKS = 60


class ProblemMapSuggestService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.graphs = GraphRepository(db)
        self.studies = PaperStudyRepository(db)
        self.repo = ProblemMapRepository(db)
        self.gateway = LLMGateway()
        self.settings = get_settings()

    # --- suggest ---

    def suggest(self, graph_id: str, text_model: str | None = None) -> ProblemMapSuggestResponse:
        self._require_graph(graph_id)
        cards = self._confirmed_cards(graph_id)
        if not cards:
            raise AppError(
                "NO_CONFIRMED_CARDS",
                "请先在「论文理解」中确认至少一篇论文的暂定理解并建立问题卡，再让模型提议关联",
                status_code=400,
            )

        existing_problems = [
            {"id": problem.id, "title": problem.title, "description": problem.description}
            for problem in self.repo.list_active_problems(graph_id)
        ]
        existing_links = [
            {"problem_card_id": link.problem_card_id, "shared_problem_id": link.shared_problem_id}
            for link in self.repo.list_active_links(graph_id)
        ]
        payload = {
            "problem_cards": cards,
            "existing_problems": existing_problems,
            "already_linked": existing_links,
        }
        raw = self._collect(
            system=PROBLEM_MAP_SUGGEST_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            text_model=text_model,
        )
        data = clean_json(raw)

        valid_card_ids = {card["id"] for card in cards}
        existing_ids = {problem["id"] for problem in existing_problems}
        problems = self._parse_problems(data.get("problems"), existing_ids)
        valid_refs = existing_ids | {item.key for item in problems}
        edges = self._parse_edges(data.get("edges"), valid_refs)
        card_links = self._parse_card_links(data.get("card_links"), valid_refs, valid_card_ids)

        return ProblemMapSuggestResponse(
            problems=problems,
            edges=edges,
            card_links=card_links,
            note=str(data.get("note") or "").strip(),
        )

    # --- apply ---

    def apply(self, graph_id: str, payload: ProblemMapApplyRequest) -> ProblemMapApplyResult:
        self._require_graph(graph_id)
        try:
            result = self._apply_inner(graph_id, payload)
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            raise

    def _apply_inner(self, graph_id: str, payload: ProblemMapApplyRequest) -> ProblemMapApplyResult:
        key_to_id: dict[str, str] = {}
        created_problems = 0
        created_edges = 0
        created_links = 0

        seen_keys: set[str] = set()
        for item in payload.problems:
            key = item.key.strip()
            title = item.title.strip()
            if not key or not title:
                raise AppError("APPLY_ITEM_INVALID", "新建问题缺少 key 或标题", status_code=400)
            if key in seen_keys:
                raise AppError("APPLY_DUPLICATE_KEY", f"问题 key {key} 重复", status_code=400)
            if self.repo.get_active_problem(key):
                raise AppError("APPLY_KEY_COLLISION", f"key {key} 与已有问题 id 冲突", status_code=400)
            seen_keys.add(key)

        for item in payload.problems:
            problem = SharedProblem(
                id=str(uuid4()),
                graph_id=graph_id,
                title=item.title.strip(),
                description=item.description.strip(),
            )
            self.repo.add_problem(problem)
            key_to_id[item.key.strip()] = problem.id
            created_problems += 1

        def resolve(ref: str) -> str:
            ref = ref.strip()
            if ref in key_to_id:
                return key_to_id[ref]
            problem = self.repo.get_active_problem(ref)
            if problem and problem.graph_id == graph_id:
                return problem.id
            raise NotFoundError("APPLY_PROBLEM_REF_NOT_FOUND", f"问题引用 {ref} 不存在")

        for item in payload.edges:
            source = resolve(item.source_ref)
            target = resolve(item.target_ref)
            if source == target:
                raise AppError("SELF_LOOP_FORBIDDEN", "层级边不能指向自身", status_code=400)
            relation_label = item.relation_label.strip() or DEFAULT_RELATION_LABEL
            if self.repo.find_active_edge_duplicate(graph_id, source, target, relation_label):
                raise ConflictError("DUPLICATE_PROBLEM_EDGE", "相同方向与标签的层级边已存在")
            self.repo.add_edge(
                SharedProblemEdge(
                    id=str(uuid4()),
                    graph_id=graph_id,
                    source_problem_id=source,
                    target_problem_id=target,
                    relation_label=relation_label,
                )
            )
            created_edges += 1

        for item in payload.card_links:
            card = self._require_card_in_graph(item.problem_card_id, graph_id)
            problem_id = resolve(item.problem_ref)
            if self.repo.find_active_link_duplicate(card.id, problem_id):
                raise ConflictError("DUPLICATE_CARD_LINK", "这张问题卡已经关联过该共享问题")
            self.repo.add_link(
                ProblemCardLink(
                    id=str(uuid4()),
                    graph_id=graph_id,
                    problem_card_id=card.id,
                    shared_problem_id=problem_id,
                    link_type=item.link_type.value,
                )
            )
            created_links += 1

        return ProblemMapApplyResult(
            created_problems=created_problems,
            created_edges=created_edges,
            created_links=created_links,
        )

    # --- helpers ---

    def _collect(self, *, system: str, messages: list[dict], text_model: str | None = None) -> str:
        content = ""
        provider, model, _ = resolve_text_route(
            text_model=text_model,
            web_search=False,
            settings=self.settings,
        )
        for chunk in self.gateway.stream(
            provider=provider,
            model=model,
            system_prompt=system,
            messages=messages,
            web_search=False,
        ):
            content += chunk.content_delta or ""
        if not content.strip():
            raise AppError("LLM_EMPTY", "模型没有返回内容", status_code=502)
        return content

    def _require_graph(self, graph_id: str) -> None:
        if not self.graphs.get_active(graph_id):
            raise NotFoundError("GRAPH_NOT_FOUND", f"Graph {graph_id} not found")

    def _confirmed_cards(self, graph_id: str) -> list[dict]:
        result: list[dict] = []
        for study in self.studies.list_studies(graph_id):
            overview = study.overview
            if not overview or overview.user_status != "CONFIRMED":
                continue
            for card in study.problem_cards:
                result.append(
                    {
                        "id": card.id,
                        "study_title": study.title,
                        "title": card.title,
                        "qualitative_overview": card.qualitative_overview,
                        "technical_interpretation": card.technical_interpretation,
                        "paper_claims": card.paper_claims,
                        "paper_not_said": card.paper_not_said,
                        "selected": card.selected,
                    }
                )
        return result

    def _parse_problems(self, value: object, existing_ids: set[str]) -> list[ProblemMapSuggestionProblem]:
        if not isinstance(value, list):
            return []
        items: list[ProblemMapSuggestionProblem] = []
        seen: set[str] = set()
        for raw in value[:MAX_PROBLEMS]:
            if not isinstance(raw, dict):
                continue
            key = str(raw.get("key") or "").strip()
            title = str(raw.get("title") or "").strip()
            if not key or not title or key in seen or key in existing_ids:
                continue
            seen.add(key)
            items.append(
                ProblemMapSuggestionProblem(
                    key=key,
                    title=title,
                    description=str(raw.get("description") or "").strip(),
                    parent_key=str(raw.get("parent_key") or "").strip() or None,
                )
            )
        return items

    def _parse_edges(self, value: object, valid_refs: set[str]) -> list[ProblemMapSuggestionEdge]:
        if not isinstance(value, list):
            return []
        items: list[ProblemMapSuggestionEdge] = []
        seen: set[tuple[str, str, str]] = set()
        for raw in value[:MAX_EDGES]:
            if not isinstance(raw, dict):
                continue
            source = str(raw.get("source_ref") or "").strip()
            target = str(raw.get("target_ref") or "").strip()
            label = str(raw.get("relation_label") or DEFAULT_RELATION_LABEL).strip() or DEFAULT_RELATION_LABEL
            if source == target or source not in valid_refs or target not in valid_refs:
                continue
            if (source, target, label) in seen:
                continue
            seen.add((source, target, label))
            items.append(
                ProblemMapSuggestionEdge(source_ref=source, target_ref=target, relation_label=label)
            )
        return items

    def _parse_card_links(
        self,
        value: object,
        valid_refs: set[str],
        valid_card_ids: set[str],
    ) -> list[ProblemMapSuggestionCardLink]:
        if not isinstance(value, list):
            return []
        items: list[ProblemMapSuggestionCardLink] = []
        seen: set[tuple[str, str]] = set()
        for raw in value[:MAX_CARD_LINKS]:
            if not isinstance(raw, dict):
                continue
            card_id = str(raw.get("problem_card_id") or "").strip()
            ref = str(raw.get("problem_ref") or "").strip()
            if card_id not in valid_card_ids or ref not in valid_refs:
                continue
            link_type = str(raw.get("link_type") or "").upper()
            if link_type not in {ProblemLinkType.CORE.value, ProblemLinkType.TOUCHED.value}:
                link_type = ProblemLinkType.TOUCHED.value
            if (card_id, ref) in seen:
                continue
            seen.add((card_id, ref))
            items.append(
                ProblemMapSuggestionCardLink(
                    problem_card_id=card_id,
                    problem_ref=ref,
                    link_type=ProblemLinkType(link_type),
                )
            )
        return items

    def _require_card_in_graph(self, card_id: str, graph_id: str) -> PaperProblemCard:
        card = self.studies.get_card(card_id)
        if not card or not card.study or card.study.graph_id != graph_id:
            raise NotFoundError("PAPER_PROBLEM_NOT_FOUND", f"问题卡 {card_id} 不在该知识图中")
        return card
