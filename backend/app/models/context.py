from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SessionContextPolicy(Base):
    __tablename__ = "session_context_policies"
    __table_args__ = (UniqueConstraint("session_id", name="uq_session_context_policy_session"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversation_sessions.id"), nullable=False)
    include_current_node_summary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_context_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    node_sources = relationship("ContextNodeSource", back_populates="policy")


class ContextNodeSource(Base):
    __tablename__ = "context_node_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    context_policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("session_context_policies.id"), nullable=False)
    source_node_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_nodes.id"), nullable=False)
    include_summary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    policy = relationship("SessionContextPolicy", back_populates="node_sources")
    session_sources = relationship("ContextSessionSource", back_populates="node_source")


class ContextSessionSource(Base):
    __tablename__ = "context_session_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    context_node_source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("context_node_sources.id"), nullable=False
    )
    source_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversation_sessions.id"), nullable=False)
    conversation_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    last_n_turns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_message_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    node_source = relationship("ContextNodeSource", back_populates="session_sources")


class ContextSnapshot(Base):
    __tablename__ = "context_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    node_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_nodes.id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversation_sessions.id"), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    rendered_system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_context: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    items = relationship("ContextSnapshotItem", back_populates="snapshot")


class ContextSnapshotItem(Base):
    __tablename__ = "context_snapshot_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("context_snapshots.id"), nullable=False)
    source_node_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rendered_content: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    snapshot = relationship("ContextSnapshot", back_populates="items")
