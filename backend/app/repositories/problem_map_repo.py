from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.paper_study import PaperProblemCard
from app.models.problem_map import ProblemCardLink, ProblemMapPosition, SharedProblem, SharedProblemEdge


class ProblemCoverage:
    def __init__(self, paper_count: int = 0, core_count: int = 0, touched_count: int = 0) -> None:
        self.paper_count = paper_count
        self.core_count = core_count
        self.touched_count = touched_count


class ProblemMapRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- shared problems ---

    def list_active_problems(self, graph_id: str) -> list[SharedProblem]:
        stmt = (
            select(SharedProblem)
            .where(SharedProblem.graph_id == graph_id, SharedProblem.deleted_at.is_(None))
            .order_by(SharedProblem.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_active_problem(self, problem_id: str) -> SharedProblem | None:
        stmt = select(SharedProblem).where(
            SharedProblem.id == problem_id,
            SharedProblem.deleted_at.is_(None),
        )
        return self.db.scalars(stmt).first()

    def add_problem(self, problem: SharedProblem) -> SharedProblem:
        self.db.add(problem)
        self.db.flush()
        return problem

    def soft_delete_problem(self, problem: SharedProblem) -> None:
        problem.deleted_at = datetime.now(UTC)
        self.db.flush()

    def coverage_counts(self, graph_id: str) -> dict[str, ProblemCoverage]:
        core_study = case((ProblemCardLink.link_type == "CORE", PaperProblemCard.study_id))
        touched_study = case((ProblemCardLink.link_type == "TOUCHED", PaperProblemCard.study_id))
        stmt = (
            select(
                ProblemCardLink.shared_problem_id,
                func.count(func.distinct(PaperProblemCard.study_id)),
                func.count(func.distinct(core_study)),
                func.count(func.distinct(touched_study)),
            )
            .join(PaperProblemCard, PaperProblemCard.id == ProblemCardLink.problem_card_id)
            .where(
                ProblemCardLink.graph_id == graph_id,
                ProblemCardLink.deleted_at.is_(None),
            )
            .group_by(ProblemCardLink.shared_problem_id)
        )
        result: dict[str, ProblemCoverage] = {}
        for problem_id, paper_count, core_count, touched_count in self.db.execute(stmt).all():
            result[problem_id] = ProblemCoverage(
                paper_count=int(paper_count or 0),
                core_count=int(core_count or 0),
                touched_count=int(touched_count or 0),
            )
        return result

    # --- hierarchy edges ---

    def list_active_edges(self, graph_id: str) -> list[SharedProblemEdge]:
        stmt = (
            select(SharedProblemEdge)
            .where(SharedProblemEdge.graph_id == graph_id, SharedProblemEdge.deleted_at.is_(None))
            .order_by(SharedProblemEdge.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_active_edge(self, edge_id: str) -> SharedProblemEdge | None:
        stmt = select(SharedProblemEdge).where(
            SharedProblemEdge.id == edge_id,
            SharedProblemEdge.deleted_at.is_(None),
        )
        return self.db.scalars(stmt).first()

    def find_active_edge_duplicate(
        self,
        graph_id: str,
        source_problem_id: str,
        target_problem_id: str,
        relation_label: str,
        exclude_edge_id: str | None = None,
    ) -> SharedProblemEdge | None:
        stmt = select(SharedProblemEdge).where(
            SharedProblemEdge.graph_id == graph_id,
            SharedProblemEdge.source_problem_id == source_problem_id,
            SharedProblemEdge.target_problem_id == target_problem_id,
            SharedProblemEdge.relation_label == relation_label,
            SharedProblemEdge.deleted_at.is_(None),
        )
        if exclude_edge_id:
            stmt = stmt.where(SharedProblemEdge.id != exclude_edge_id)
        return self.db.scalars(stmt).first()

    def count_active_edges_for_problem(self, problem_id: str) -> int:
        stmt = select(SharedProblemEdge).where(
            SharedProblemEdge.deleted_at.is_(None),
            (SharedProblemEdge.source_problem_id == problem_id)
            | (SharedProblemEdge.target_problem_id == problem_id),
        )
        return len(list(self.db.scalars(stmt).all()))

    def add_edge(self, edge: SharedProblemEdge) -> SharedProblemEdge:
        self.db.add(edge)
        self.db.flush()
        return edge

    def soft_delete_edge(self, edge: SharedProblemEdge) -> None:
        edge.deleted_at = datetime.now(UTC)
        self.db.flush()

    # --- card links ---

    def list_active_links(self, graph_id: str) -> list[ProblemCardLink]:
        stmt = (
            select(ProblemCardLink)
            .where(ProblemCardLink.graph_id == graph_id, ProblemCardLink.deleted_at.is_(None))
            .order_by(ProblemCardLink.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_active_link(self, link_id: str) -> ProblemCardLink | None:
        stmt = select(ProblemCardLink).where(
            ProblemCardLink.id == link_id,
            ProblemCardLink.deleted_at.is_(None),
        )
        return self.db.scalars(stmt).first()

    def find_active_link_duplicate(
        self,
        problem_card_id: str,
        shared_problem_id: str,
        exclude_link_id: str | None = None,
    ) -> ProblemCardLink | None:
        stmt = select(ProblemCardLink).where(
            ProblemCardLink.problem_card_id == problem_card_id,
            ProblemCardLink.shared_problem_id == shared_problem_id,
            ProblemCardLink.deleted_at.is_(None),
        )
        if exclude_link_id:
            stmt = stmt.where(ProblemCardLink.id != exclude_link_id)
        return self.db.scalars(stmt).first()

    def count_active_links_for_problem(self, problem_id: str) -> int:
        stmt = select(ProblemCardLink).where(
            ProblemCardLink.shared_problem_id == problem_id,
            ProblemCardLink.deleted_at.is_(None),
        )
        return len(list(self.db.scalars(stmt).all()))

    def add_link(self, link: ProblemCardLink) -> ProblemCardLink:
        self.db.add(link)
        self.db.flush()
        return link

    def soft_delete_link(self, link: ProblemCardLink) -> None:
        link.deleted_at = datetime.now(UTC)
        self.db.flush()

    # --- positions ---

    def list_positions(self, graph_id: str) -> list[ProblemMapPosition]:
        stmt = (
            select(ProblemMapPosition)
            .where(ProblemMapPosition.graph_id == graph_id)
            .order_by(ProblemMapPosition.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_position(self, graph_id: str, entity_type: str, entity_id: str) -> ProblemMapPosition | None:
        stmt = select(ProblemMapPosition).where(
            ProblemMapPosition.graph_id == graph_id,
            ProblemMapPosition.entity_type == entity_type,
            ProblemMapPosition.entity_id == entity_id,
        )
        return self.db.scalars(stmt).first()

    def add_position(self, position: ProblemMapPosition) -> ProblemMapPosition:
        self.db.add(position)
        self.db.flush()
        return position
