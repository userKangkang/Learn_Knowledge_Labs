from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SharedProblem(Base):
    __tablename__ = "shared_problems"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    graph_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_graphs.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    out_edges = relationship(
        "SharedProblemEdge",
        foreign_keys="SharedProblemEdge.source_problem_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    in_edges = relationship(
        "SharedProblemEdge",
        foreign_keys="SharedProblemEdge.target_problem_id",
        back_populates="target",
        cascade="all, delete-orphan",
    )
    links = relationship("ProblemCardLink", back_populates="problem", cascade="all, delete-orphan")


class SharedProblemEdge(Base):
    __tablename__ = "shared_problem_edges"
    __table_args__ = (
        UniqueConstraint(
            "graph_id",
            "source_problem_id",
            "target_problem_id",
            "relation_label",
            name="uq_shared_problem_edge",
        ),
        Index("ix_shared_problem_edges_endpoints", "source_problem_id", "target_problem_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    graph_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_graphs.id"), nullable=False, index=True)
    source_problem_id: Mapped[str] = mapped_column(String(36), ForeignKey("shared_problems.id"), nullable=False)
    target_problem_id: Mapped[str] = mapped_column(String(36), ForeignKey("shared_problems.id"), nullable=False)
    relation_label: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source = relationship("SharedProblem", foreign_keys=[source_problem_id], back_populates="out_edges")
    target = relationship("SharedProblem", foreign_keys=[target_problem_id], back_populates="in_edges")


class ProblemCardLink(Base):
    __tablename__ = "problem_card_links"
    __table_args__ = (
        UniqueConstraint("problem_card_id", "shared_problem_id", name="uq_problem_card_link"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    graph_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_graphs.id"), nullable=False, index=True)
    problem_card_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("paper_problem_cards.id"),
        nullable=False,
        index=True,
    )
    shared_problem_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("shared_problems.id"),
        nullable=False,
        index=True,
    )
    link_type: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    card = relationship("PaperProblemCard", back_populates="problem_links")
    problem = relationship("SharedProblem", back_populates="links")


class ProblemMapPosition(Base):
    __tablename__ = "problem_map_positions"
    __table_args__ = (
        UniqueConstraint("graph_id", "entity_type", "entity_id", name="uq_problem_map_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    graph_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_graphs.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
