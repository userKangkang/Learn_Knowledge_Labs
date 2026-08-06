"""add paper understanding dialogue stages

Revision ID: 012
Revises: 011
Create Date: 2026-08-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, Sequence[str], None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_study_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("study_id", sa.String(length=36), sa.ForeignKey("paper_studies.id"), nullable=False),
        sa.Column("stage", sa.String(length=24), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.UniqueConstraint("study_id", "stage", "sequence_index", name="uq_paper_study_message_order"),
    )
    op.create_index("ix_paper_study_messages_study_id", "paper_study_messages", ["study_id"])


def downgrade() -> None:
    op.drop_table("paper_study_messages")
