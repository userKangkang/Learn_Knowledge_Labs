from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel, TimestampRead


class ProblemLinkType(StrEnum):
    CORE = "CORE"
    TOUCHED = "TOUCHED"


class SharedProblemCreate(APIModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=20000)


class SharedProblemUpdate(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)


class SharedProblemRead(TimestampRead):
    id: str
    graph_id: str
    title: str
    description: str = ""


class SharedProblemWithCoverage(SharedProblemRead):
    coverage_paper_count: int = 0
    coverage_core_count: int = 0
    coverage_touched_count: int = 0


class SharedProblemEdgeCreate(APIModel):
    source_problem_id: str
    target_problem_id: str
    relation_label: str = Field(default="SPECIALIZES_INTO", min_length=1, max_length=255)


class SharedProblemEdgeUpdate(APIModel):
    relation_label: str | None = Field(default=None, min_length=1, max_length=255)
    reverse: bool = False


class SharedProblemEdgeRead(APIModel):
    id: str
    graph_id: str
    source_problem_id: str
    target_problem_id: str
    relation_label: str
    created_at: datetime


class ProblemCardLinkCreate(APIModel):
    shared_problem_id: str
    link_type: ProblemLinkType | None = None


class ProblemCardLinkUpdate(APIModel):
    link_type: ProblemLinkType


class ProblemCardLinkRead(APIModel):
    id: str
    graph_id: str
    problem_card_id: str
    shared_problem_id: str
    link_type: ProblemLinkType
    created_at: datetime


class ProblemMapPaperCard(APIModel):
    id: str
    title: str
    qualitative_overview: str = ""
    selected: bool


class ProblemMapPaper(APIModel):
    study_id: str
    title: str
    research_context: str = ""
    core_problem: str = ""
    main_approach: str = ""
    cards: list[ProblemMapPaperCard] = []


class RelatedPaperSearchTurn(APIModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=30000)


class RelatedPaperSearchRequest(APIModel):
    study_ids: list[str] = Field(min_length=1, max_length=12)
    model: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1, max_length=12000)
    ccf_a_only: bool = False
    prior_turns: list[RelatedPaperSearchTurn] = Field(default_factory=list, max_length=20)


class ProblemMapPositionItem(APIModel):
    entity_type: Literal["PAPER", "CARD", "PROBLEM"]
    entity_id: str
    position_x: float = 0
    position_y: float = 0


class ProblemMapPositionRead(ProblemMapPositionItem):
    id: str
    graph_id: str


class ProblemMapBundleRead(APIModel):
    problems: list[SharedProblemWithCoverage] = []
    edges: list[SharedProblemEdgeRead] = []
    links: list[ProblemCardLinkRead] = []
    papers: list[ProblemMapPaper] = []
    positions: list[ProblemMapPositionRead] = []


class ProblemMapSuggestionProblem(APIModel):
    key: str
    title: str
    description: str = ""
    parent_key: str | None = None


class ProblemMapSuggestionEdge(APIModel):
    source_ref: str
    target_ref: str
    relation_label: str = "SPECIALIZES_INTO"


class ProblemMapSuggestionCardLink(APIModel):
    problem_card_id: str
    problem_ref: str
    link_type: ProblemLinkType = ProblemLinkType.TOUCHED


class ProblemMapSuggestResponse(APIModel):
    problems: list[ProblemMapSuggestionProblem] = []
    edges: list[ProblemMapSuggestionEdge] = []
    card_links: list[ProblemMapSuggestionCardLink] = []
    note: str = ""


class ProblemMapApplyProblem(APIModel):
    key: str
    title: str
    description: str = ""


class ProblemMapApplyEdge(APIModel):
    source_ref: str
    target_ref: str
    relation_label: str = "SPECIALIZES_INTO"


class ProblemMapApplyCardLink(APIModel):
    problem_card_id: str
    problem_ref: str
    link_type: ProblemLinkType = ProblemLinkType.TOUCHED


class ProblemMapApplyRequest(APIModel):
    problems: list[ProblemMapApplyProblem] = []
    edges: list[ProblemMapApplyEdge] = []
    card_links: list[ProblemMapApplyCardLink] = []


class ProblemMapApplyResult(APIModel):
    created_problems: int
    created_edges: int
    created_links: int
