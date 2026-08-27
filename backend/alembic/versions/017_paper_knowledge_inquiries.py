"""paper overview temporary knowledge inquiries

Revision ID: 017
Revises: 016
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "017"
down_revision: Union[str, Sequence[str], None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_knowledge_inquiries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("study_id", sa.String(length=36), sa.ForeignKey("paper_studies.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="ACTIVE"),
        sa.Column("graph_node_id", sa.String(length=36), sa.ForeignKey("knowledge_nodes.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
    )
    op.create_index("ix_paper_knowledge_inquiries_study_id", "paper_knowledge_inquiries", ["study_id"])
    op.create_table(
        "paper_knowledge_inquiry_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("inquiry_id", sa.String(length=36), sa.ForeignKey("paper_knowledge_inquiries.id"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.UniqueConstraint("inquiry_id", "sequence_index", name="uq_paper_knowledge_inquiry_message_order"),
    )
    op.create_index("ix_paper_knowledge_inquiry_messages_inquiry_id", "paper_knowledge_inquiry_messages", ["inquiry_id"])


def downgrade() -> None:
    op.drop_index("ix_paper_knowledge_inquiry_messages_inquiry_id", table_name="paper_knowledge_inquiry_messages")
    op.drop_table("paper_knowledge_inquiry_messages")
    op.drop_index("ix_paper_knowledge_inquiries_study_id", table_name="paper_knowledge_inquiries")
    op.drop_table("paper_knowledge_inquiries")
