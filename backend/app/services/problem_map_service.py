from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import AppError, ConflictError, NotFoundError
from app.models.paper_study import PaperProblemCard
from app.models.problem_map import ProblemCardLink, ProblemMapPosition, SharedProblem, SharedProblemEdge
from app.repositories.graph_repo import GraphRepository
from app.repositories.paper_study_repo import PaperStudyRepository
from app.repositories.problem_map_repo import ProblemCoverage, ProblemMapRepository
from app.schemas.problem_map import (
    ProblemCardLinkCreate,
    ProblemCardLinkUpdate,
    ProblemLinkType,
    ProblemMapPositionItem,
    SharedProblemCreate,
    SharedProblemEdgeCreate,
    SharedProblemEdgeUpdate,
    SharedProblemUpdate,
)

DEFAULT_RELATION_LABEL = "SPECIALIZES_INTO"


class ProblemMapService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.graphs = GraphRepository(db)
        self.studies = PaperStudyRepository(db)
        self.repo = ProblemMapRepository(db)

    # --- shared problems ---

    def list_problems(self, graph_id: str) -> list[dict]:
        self._require_graph(graph_id)
        coverage = self.repo.coverage_counts(graph_id)
        return [self._problem_read(problem, coverage.get(problem.id, ProblemCoverage())) for problem in self.repo.list_active_problems(graph_id)]

    def get_problem(self, problem_id: str) -> dict:
        problem = self._require_problem(problem_id)
        coverage = self.repo.coverage_counts(problem.graph_id)
        return self._problem_read(problem, coverage.get(problem.id, ProblemCoverage()))

    def create_problem(self, graph_id: str, payload: SharedProblemCreate) -> dict:
        self._require_graph(graph_id)
        title = payload.title.strip()
        if not title:
            raise AppError("TITLE_REQUIRED", "共享问题标题不能为空", status_code=400)
        problem = SharedProblem(
            id=str(uuid4()),
            graph_id=graph_id,
            title=title,
            description=payload.description.strip(),
        )
        self.repo.add_problem(problem)
        self.db.commit()
        self.db.refresh(problem)
        return self._problem_read(problem, ProblemCoverage())

    def update_problem(self, problem_id: str, payload: SharedProblemUpdate) -> dict:
        problem = self._require_problem(problem_id)
        if payload.title is not None:
            problem.title = payload.title.strip()
        if payload.description is not None:
            problem.description = payload.description.strip()
        self.db.commit()
        self.db.refresh(problem)
        coverage = self.repo.coverage_counts(problem.graph_id)
        return self._problem_read(problem, coverage.get(problem.id, ProblemCoverage()))

    def delete_problem(self, problem_id: str) -> None:
        problem = self._require_problem(problem_id)
        if self.repo.count_active_edges_for_problem(problem.id) > 0:
            raise ConflictError(
                "PROBLEM_HAS_EDGES",
                "该共享问题仍有关联的层级边，请先删除或解除边",
            )
        if self.repo.count_active_links_for_problem(problem.id) > 0:
            raise ConflictError(
                "PROBLEM_HAS_CARD_LINKS",
                "该共享问题仍有关联的问题卡，请先解除关联",
            )
        self.repo.soft_delete_problem(problem)
        self.db.commit()

    # --- hierarchy edges ---

    def list_edges(self, graph_id: str) -> list[SharedProblemEdge]:
        self._require_graph(graph_id)
        return self.repo.list_active_edges(graph_id)

    def create_edge(self, graph_id: str, payload: SharedProblemEdgeCreate) -> SharedProblemEdge:
        self._require_graph(graph_id)
        self._validate_problem_endpoints(graph_id, payload.source_problem_id, payload.target_problem_id)
        relation_label = payload.relation_label.strip()
        if not relation_label:
            raise AppError("RELATION_LABEL_REQUIRED", "层级边标签不能为空", status_code=400)
        duplicate = self.repo.find_active_edge_duplicate(
            graph_id=graph_id,
            source_problem_id=payload.source_problem_id,
            target_problem_id=payload.target_problem_id,
            relation_label=relation_label,
        )
        if duplicate:
            raise ConflictError(
                "DUPLICATE_PROBLEM_EDGE",
                "相同方向与标签的层级边已存在",
            )
        edge = SharedProblemEdge(
            id=str(uuid4()),
            graph_id=graph_id,
            source_problem_id=payload.source_problem_id,
            target_problem_id=payload.target_problem_id,
            relation_label=relation_label,
        )
        self.repo.add_edge(edge)
        self.db.commit()
        self.db.refresh(edge)
        return edge

    def update_edge(self, edge_id: str, payload: SharedProblemEdgeUpdate) -> SharedProblemEdge:
        edge = self._require_edge(edge_id)
        next_source = edge.target_problem_id if payload.reverse else edge.source_problem_id
        next_target = edge.source_problem_id if payload.reverse else edge.target_problem_id
        next_label = payload.relation_label.strip() if payload.relation_label is not None else edge.relation_label
        if payload.reverse:
            self._validate_problem_endpoints(edge.graph_id, next_source, next_target)
        duplicate = self.repo.find_active_edge_duplicate(
            graph_id=edge.graph_id,
            source_problem_id=next_source,
            target_problem_id=next_target,
            relation_label=next_label,
            exclude_edge_id=edge.id,
        )
        if duplicate:
            raise ConflictError(
                "DUPLICATE_PROBLEM_EDGE",
                "相同方向与标签的层级边已存在",
            )
        edge.source_problem_id = next_source
        edge.target_problem_id = next_target
        edge.relation_label = next_label
        self.db.commit()
        self.db.refresh(edge)
        return edge

    def delete_edge(self, edge_id: str) -> None:
        edge = self._require_edge(edge_id)
        self.repo.soft_delete_edge(edge)
        self.db.commit()

    # --- card links ---

    def list_links(self, graph_id: str) -> list[ProblemCardLink]:
        self._require_graph(graph_id)
        return self.repo.list_active_links(graph_id)

    def create_link(self, card_id: str, payload: ProblemCardLinkCreate) -> ProblemCardLink:
        card = self._require_card(card_id)
        problem = self._require_problem_in_graph(payload.shared_problem_id, card.study.graph_id)
        link_type = payload.link_type if payload.link_type is not None else self._default_link_type(card)
        duplicate = self.repo.find_active_link_duplicate(card.id, problem.id)
        if duplicate:
            raise ConflictError(
                "DUPLICATE_CARD_LINK",
                "这张问题卡已经关联过该共享问题",
            )
        link = ProblemCardLink(
            id=str(uuid4()),
            graph_id=card.study.graph_id,
            problem_card_id=card.id,
            shared_problem_id=problem.id,
            link_type=link_type.value,
        )
        self.repo.add_link(link)
        self.db.commit()
        self.db.refresh(link)
        return link

    def update_link(self, link_id: str, payload: ProblemCardLinkUpdate) -> ProblemCardLink:
        link = self._require_link(link_id)
        link.link_type = payload.link_type.value
        self.db.commit()
        self.db.refresh(link)
        return link

    def delete_link(self, link_id: str) -> None:
        link = self._require_link(link_id)
        self.repo.soft_delete_link(link)
        self.db.commit()

    # --- positions ---

    def save_positions(self, graph_id: str, items: list[ProblemMapPositionItem]) -> list[ProblemMapPosition]:
        self._require_graph(graph_id)
        saved: list[ProblemMapPosition] = []
        for item in items:
            self._validate_position_entity(graph_id, item)
            position = self.repo.get_position(graph_id, item.entity_type, item.entity_id)
            if position is None:
                position = ProblemMapPosition(
                    id=str(uuid4()),
                    graph_id=graph_id,
                    entity_type=item.entity_type,
                    entity_id=item.entity_id,
                    position_x=item.position_x,
                    position_y=item.position_y,
                )
                self.repo.add_position(position)
            else:
                position.position_x = item.position_x
                position.position_y = item.position_y
            saved.append(position)
        self.db.commit()
        for position in saved:
            self.db.refresh(position)
        return saved

    # --- bundle ---

    def get_problem_map(self, graph_id: str) -> dict:
        self._require_graph(graph_id)
        coverage = self.repo.coverage_counts(graph_id)
        problems = [
            self._problem_read(problem, coverage.get(problem.id, ProblemCoverage()))
            for problem in self.repo.list_active_problems(graph_id)
        ]
        papers = []
        for study in self.studies.list_studies(graph_id):
            overview = self.studies.get_overview(study.id)
            papers.append(
                {
                    "study_id": study.id,
                    "title": study.title,
                    "research_context": overview.research_context if overview else "",
                    "core_problem": overview.core_problem if overview else "",
                    "main_approach": overview.main_approach if overview else "",
                    "cards": [
                        {
                            "id": card.id,
                            "title": card.title,
                            "qualitative_overview": card.qualitative_overview,
                            "selected": card.selected,
                        }
                        for card in study.problem_cards
                    ],
                }
            )
        return {
            "problems": problems,
            "edges": self.repo.list_active_edges(graph_id),
            "links": self.repo.list_active_links(graph_id),
            "papers": papers,
            "positions": self.repo.list_positions(graph_id),
        }

    # --- helpers ---

    def _require_graph(self, graph_id: str) -> None:
        if not self.graphs.get_active(graph_id):
            raise NotFoundError("GRAPH_NOT_FOUND", f"Graph {graph_id} not found")

    def _require_problem(self, problem_id: str) -> SharedProblem:
        problem = self.repo.get_active_problem(problem_id)
        if not problem:
            raise NotFoundError("SHARED_PROBLEM_NOT_FOUND", f"Shared problem {problem_id} not found")
        return problem

    def _require_problem_in_graph(self, problem_id: str, graph_id: str) -> SharedProblem:
        problem = self._require_problem(problem_id)
        if problem.graph_id != graph_id:
            raise NotFoundError("SHARED_PROBLEM_NOT_FOUND", f"Shared problem {problem_id} not found in graph")
        return problem

    def _require_card(self, card_id: str) -> PaperProblemCard:
        card = self.studies.get_card(card_id)
        if not card or not card.study:
            raise NotFoundError("PAPER_PROBLEM_NOT_FOUND", f"Problem card {card_id} not found")
        return card

    def _require_edge(self, edge_id: str) -> SharedProblemEdge:
        edge = self.repo.get_active_edge(edge_id)
        if not edge:
            raise NotFoundError("PROBLEM_EDGE_NOT_FOUND", f"Problem edge {edge_id} not found")
        return edge

    def _require_link(self, link_id: str) -> ProblemCardLink:
        link = self.repo.get_active_link(link_id)
        if not link:
            raise NotFoundError("CARD_LINK_NOT_FOUND", f"Card link {link_id} not found")
        return link

    def _validate_problem_endpoints(self, graph_id: str, source_problem_id: str, target_problem_id: str) -> None:
        if source_problem_id == target_problem_id:
            raise AppError("SELF_LOOP_FORBIDDEN", "层级边不能指向自身", status_code=400)
        self._require_problem_in_graph(source_problem_id, graph_id)
        self._require_problem_in_graph(target_problem_id, graph_id)

    def _validate_position_entity(self, graph_id: str, item: ProblemMapPositionItem) -> None:
        if item.entity_type == "PROBLEM":
            self._require_problem_in_graph(item.entity_id, graph_id)
            return
        if item.entity_type == "CARD":
            card = self._require_card(item.entity_id)
            if card.study.graph_id != graph_id:
                raise NotFoundError("PAPER_PROBLEM_NOT_FOUND", f"Problem card {item.entity_id} not found in graph")
            return
        study = self.studies.get_study(item.entity_id)
        if not study or study.graph_id != graph_id:
            raise NotFoundError("PAPER_STUDY_NOT_FOUND", f"Paper study {item.entity_id} not found in graph")

    @staticmethod
    def _default_link_type(card) -> ProblemLinkType:
        return ProblemLinkType.CORE if card.selected else ProblemLinkType.TOUCHED

    @staticmethod
    def _problem_read(problem: SharedProblem, coverage: ProblemCoverage) -> dict:
        return {
            "id": problem.id,
            "graph_id": problem.graph_id,
            "title": problem.title,
            "description": problem.description,
            "created_at": problem.created_at,
            "updated_at": problem.updated_at,
            "coverage_paper_count": coverage.paper_count,
            "coverage_core_count": coverage.core_count,
            "coverage_touched_count": coverage.touched_count,
        }
