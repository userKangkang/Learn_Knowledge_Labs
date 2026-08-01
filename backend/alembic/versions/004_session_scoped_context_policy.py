"""session scoped context policy

Revision ID: 004
Revises: 003
Create Date: 2026-07-31

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, Sequence[str], None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_context_session_sources_node_source_order", table_name="context_session_sources")
    op.drop_table("context_session_sources")
    op.drop_index("ix_context_node_sources_policy_order", table_name="context_node_sources")
    op.drop_table("context_node_sources")
    op.drop_table("node_context_policies")

    op.create_table(
        "session_context_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("include_current_node_summary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_context_tokens", sa.Integer(), nullable=True),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["conversation_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_session_context_policy_session"),
    )

    op.create_table(
        "context_node_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("context_policy_id", sa.String(length=36), nullable=False),
        sa.Column("source_node_id", sa.String(length=36), nullable=False),
        sa.Column("include_summary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["context_policy_id"], ["session_context_policies.id"]),
        sa.ForeignKeyConstraint(["source_node_id"], ["knowledge_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_context_node_sources_policy_order",
        "context_node_sources",
        ["context_policy_id", "order_index"],
        unique=False,
    )

    op.create_table(
        "context_session_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("context_node_source_id", sa.String(length=36), nullable=False),
        sa.Column("source_session_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_mode", sa.String(length=32), nullable=False),
        sa.Column("last_n_turns", sa.Integer(), nullable=True),
        sa.Column("selected_message_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["context_node_source_id"], ["context_node_sources.id"]),
        sa.ForeignKeyConstraint(["source_session_id"], ["conversation_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_context_session_sources_node_source_order",
        "context_session_sources",
        ["context_node_source_id", "order_index"],
        unique=False,
    )


def downgrade() -> None:
    # Downgrade rebuilds the previous node-scoped schema (lossy).
    op.drop_index("ix_context_session_sources_node_source_order", table_name="context_session_sources")
    op.drop_table("context_session_sources")
    op.drop_index("ix_context_node_sources_policy_order", table_name="context_node_sources")
    op.drop_table("context_node_sources")
    op.drop_table("session_context_policies")

    op.create_table(
        "node_context_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("node_id", sa.String(length=36), nullable=False),
        sa.Column("include_current_node_summary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("include_current_session_history", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_context_tokens", sa.Integer(), nullable=True),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["node_id"], ["knowledge_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("node_id", name="uq_node_context_policy_node"),
    )
    op.create_table(
        "context_node_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("context_policy_id", sa.String(length=36), nullable=False),
        sa.Column("source_node_id", sa.String(length=36), nullable=False),
        sa.Column("include_summary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["context_policy_id"], ["node_context_policies.id"]),
        sa.ForeignKeyConstraint(["source_node_id"], ["knowledge_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_context_node_sources_policy_order",
        "context_node_sources",
        ["context_policy_id", "order_index"],
        unique=False,
    )
    op.create_table(
        "context_session_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("context_node_source_id", sa.String(length=36), nullable=False),
        sa.Column("source_session_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_mode", sa.String(length=32), nullable=False),
        sa.Column("last_n_turns", sa.Integer(), nullable=True),
        sa.Column("selected_message_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["context_node_source_id"], ["context_node_sources.id"]),
        sa.ForeignKeyConstraint(["source_session_id"], ["conversation_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_context_session_sources_node_source_order",
        "context_session_sources",
        ["context_node_source_id", "order_index"],
        unique=False,
    )
