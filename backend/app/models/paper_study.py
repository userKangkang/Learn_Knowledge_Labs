from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PaperStudy(Base):
    __tablename__ = "paper_studies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    graph_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_graphs.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="OVERVIEW")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    document = relationship("PaperStudyDocument", back_populates="study", uselist=False, cascade="all, delete-orphan")
    overview = relationship("PaperStudyOverview", back_populates="study", uselist=False, cascade="all, delete-orphan")
    messages = relationship("PaperStudyMessage", back_populates="study", cascade="all, delete-orphan")
    problem_cards = relationship("PaperProblemCard", back_populates="study", cascade="all, delete-orphan")
    knowledge_inquiries = relationship("PaperKnowledgeInquiry", back_populates="study", cascade="all, delete-orphan")


class PaperStudyDocument(Base):
    __tablename__ = "paper_study_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    study_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_studies.id"), nullable=False, unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    kimi_detailed_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="UPLOADED")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    study = relationship("PaperStudy", back_populates="document")
    references = relationship("KnowledgeNodePaperReference", back_populates="document", cascade="all, delete-orphan")


class PaperStudyOverview(Base):
    __tablename__ = "paper_study_overviews"

    study_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_studies.id"), primary_key=True)
    research_context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    core_problem: Mapped[str] = mapped_column(Text, nullable=False, default="")
    main_approach: Mapped[str] = mapped_column(Text, nullable=False, default="")
    claimed_effect: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_understanding: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_status: Mapped[str] = mapped_column(String(24), nullable=False, default="DRAFT")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    study = relationship("PaperStudy", back_populates="overview")


class PaperStudyMessage(Base):
    __tablename__ = "paper_study_messages"
    __table_args__ = (UniqueConstraint("study_id", "stage", "sequence_index", name="uq_paper_study_message_order"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    study_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_studies.id"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(24), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    study = relationship("PaperStudy", back_populates="messages")


class PaperKnowledgeInquiry(Base):
    __tablename__ = "paper_knowledge_inquiries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    study_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_studies.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")
    graph_node_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("knowledge_nodes.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    study = relationship("PaperStudy", back_populates="knowledge_inquiries")
    messages = relationship("PaperKnowledgeInquiryMessage", back_populates="inquiry", cascade="all, delete-orphan")


class PaperKnowledgeInquiryMessage(Base):
    __tablename__ = "paper_knowledge_inquiry_messages"
    __table_args__ = (UniqueConstraint("inquiry_id", "sequence_index", name="uq_paper_knowledge_inquiry_message_order"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inquiry_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_knowledge_inquiries.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    inquiry = relationship("PaperKnowledgeInquiry", back_populates="messages")


class PaperProblemCard(Base):
    __tablename__ = "paper_problem_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    study_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_studies.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    qualitative_overview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    technical_interpretation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    paper_claims: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    paper_not_said: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    user_interest: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_stuck_point: Mapped[str] = mapped_column(Text, nullable=False, default="")
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="UNOPENED")
    verification_anchor: Mapped[str] = mapped_column(Text, nullable=False, default="")
    verification_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    verification_answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    study = relationship("PaperStudy", back_populates="problem_cards")
    concept_map = relationship("PaperConceptMap", back_populates="problem_card", uselist=False, cascade="all, delete-orphan")
    problem_links = relationship("ProblemCardLink", back_populates="card", cascade="all, delete-orphan")


class PaperConceptMap(Base):
    __tablename__ = "paper_concept_maps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    problem_card_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_problem_cards.id"), nullable=False, unique=True, index=True)
    workflow_stage: Mapped[str] = mapped_column(String(24), nullable=False, default="EMPTY")
    landscape_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    candidate_review_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confirmed_candidate_keys_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    problem_card = relationship("PaperProblemCard", back_populates="concept_map")
    items = relationship("PaperConceptItem", back_populates="concept_map", cascade="all, delete-orphan")
    relations = relationship("PaperConceptRelation", back_populates="concept_map", cascade="all, delete-orphan")


class PaperConceptItem(Base):
    __tablename__ = "paper_concept_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    concept_map_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_concept_maps.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    paper_anchor: Mapped[str] = mapped_column(Text, nullable=False, default="")
    graph_node_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("knowledge_nodes.id"), nullable=True)
    user_status: Mapped[str] = mapped_column(String(24), nullable=False, default="NEEDS_WORK")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    concept_map = relationship("PaperConceptMap", back_populates="items")


class PaperConceptRelation(Base):
    __tablename__ = "paper_concept_relations"
    __table_args__ = (UniqueConstraint("concept_map_id", "source_item_id", "target_item_id", name="uq_paper_concept_relation"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    concept_map_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_concept_maps.id"), nullable=False, index=True)
    source_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_concept_items.id"), nullable=False)
    target_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_concept_items.id"), nullable=False)
    relation_label: Mapped[str] = mapped_column(String(255), nullable=False)

    concept_map = relationship("PaperConceptMap", back_populates="relations")


class KnowledgeNodePaperReference(Base):
    __tablename__ = "knowledge_node_paper_references"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    node_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_nodes.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("paper_study_documents.id"), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    link_type: Mapped[str] = mapped_column(String(32), nullable=False, default="MECHANISM")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("PaperStudyDocument", back_populates="references")
    node = relationship("KnowledgeNode", back_populates="paper_references")
