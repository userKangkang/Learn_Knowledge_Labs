from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel, TimestampRead


DocumentStatus = Literal["UPLOADED", "ANALYZING", "READY", "FAILED"]
ConceptCategory = Literal["MUST", "ON_DEMAND", "EXTENSION"]
ConceptWorkflowStage = Literal["EMPTY", "LANDSCAPE", "REVIEW", "COMPLETED"]
UnderstandingLevel = Literal["NEEDS_WORK", "BASIC", "DEEP"]
UnderstandingStatus = Literal["DRAFT", "CONFIRMED", "NEEDS_REVISION"]
VerificationStatus = Literal["PENDING", "CAN_EXPLAIN", "PARTLY", "STILL_STUCK"]
PaperStudyStage = Literal["OVERVIEW", "PROBLEM_MAP"]


class PaperStudyCreate(APIModel):
    title: str = Field(min_length=1, max_length=255)


class PaperStudyUpdate(APIModel):
    title: str = Field(min_length=1, max_length=255)


class PaperDocumentRead(TimestampRead):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    source_text_char_count: int = 0
    kimi_detailed_analysis: str | None = None
    error: str | None = None


class PaperSourceTextPreviewRead(APIModel):
    filename: str
    content: str
    character_count: int
    extraction_note: str


class PaperOverviewRead(APIModel):
    research_context: str = ""
    core_problem: str = ""
    main_approach: str = ""
    claimed_effect: str = ""
    user_understanding: str = ""
    user_status: UnderstandingStatus = "DRAFT"


class PaperOverviewUpdate(APIModel):
    research_context: str | None = None
    core_problem: str | None = None
    main_approach: str | None = None
    claimed_effect: str | None = None
    user_understanding: str | None = None
    user_status: UnderstandingStatus | None = None


class PaperStudyMessageCreate(APIModel):
    stage: PaperStudyStage
    content: str = Field(min_length=1, max_length=12000)
    text_model: str | None = None


class PaperStudyMessageRead(APIModel):
    id: str
    study_id: str
    stage: PaperStudyStage
    role: Literal["USER", "ASSISTANT"]
    content: str
    sequence_index: int
    created_at: datetime


class PaperProblemCardRead(TimestampRead):
    id: str
    study_id: str
    title: str
    qualitative_overview: str
    technical_interpretation: str
    paper_claims: list[str] = []
    paper_not_said: list[str] = []
    user_interest: str
    user_stuck_point: str
    selected: bool
    status: str
    verification_anchor: str
    verification_prompt: str
    verification_answer: str
    verification_status: VerificationStatus
    order_index: int


class PaperProblemCardCreate(APIModel):
    title: str
    qualitative_overview: str = ""
    technical_interpretation: str = ""
    paper_claims: list[str] = []
    paper_not_said: list[str] = []
    verification_anchor: str = ""
    verification_prompt: str = ""


class PaperProblemCardUpdate(APIModel):
    title: str | None = None
    qualitative_overview: str | None = None
    technical_interpretation: str | None = None
    paper_claims: list[str] | None = None
    paper_not_said: list[str] | None = None
    user_interest: str | None = None
    user_stuck_point: str | None = None
    selected: bool | None = None
    status: str | None = None
    verification_anchor: str | None = None
    verification_prompt: str | None = None
    verification_answer: str | None = None
    verification_status: VerificationStatus | None = None


class PaperConceptItemRead(APIModel):
    id: str
    title: str
    explanation: str
    category: ConceptCategory
    paper_anchor: str
    graph_node_id: str | None
    user_status: UnderstandingLevel
    order_index: int


class PaperConceptRelationRead(APIModel):
    id: str
    source_item_id: str
    target_item_id: str
    relation_label: str


class PaperConceptMapRead(APIModel):
    id: str
    problem_card_id: str
    workflow_stage: ConceptWorkflowStage = "EMPTY"
    landscape_items: list[dict] = []
    candidate_review: list[dict] = []
    confirmed_candidate_keys: list[str] = []
    items: list[PaperConceptItemRead] = []
    relations: list[PaperConceptRelationRead] = []


class PaperConceptItemUpdate(APIModel):
    user_status: UnderstandingLevel | None = None


class PaperConceptFinalize(APIModel):
    confirmed_candidate_keys: list[str] = []
    text_model: str | None = None


class PaperTextModelSelect(APIModel):
    text_model: str | None = None


class AttachConceptNode(APIModel):
    existing_node_id: str | None = None
    create_node: bool = False
    position_x: float = 0
    position_y: float = 0
    location: str = ""
    link_type: Literal["PROBLEM_EVIDENCE", "MECHANISM", "RESULT", "BASELINE"] = "MECHANISM"
    note: str = ""


class PaperStudyRead(TimestampRead):
    id: str
    graph_id: str
    title: str
    status: str
    document: PaperDocumentRead | None = None
    overview: PaperOverviewRead = Field(default_factory=PaperOverviewRead)
    messages: list[PaperStudyMessageRead] = []
    problem_cards: list[PaperProblemCardRead] = []
