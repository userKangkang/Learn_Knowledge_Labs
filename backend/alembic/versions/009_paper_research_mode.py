"""paper research mode

Revision ID: 009
Revises: 008
Create Date: 2026-08-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, Sequence[str], None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "direction_workshops",
        sa.Column("mode", sa.String(length=24), nullable=False, server_default="GENERAL"),
    )
    op.add_column(
        "direction_workshops",
        sa.Column("include_graph_context", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "learning_planning_papers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "workshop_id",
            sa.String(length=36),
            sa.ForeignKey("direction_workshops.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False, server_default="pdf"),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="UPLOADED"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
    )
    op.create_index(
        "ix_learning_planning_papers_workshop_id",
        "learning_planning_papers",
        ["workshop_id"],
        unique=True,
    )

    op.add_column("problem_directions", sa.Column("motivation", sa.Text(), nullable=False, server_default=""))
    op.add_column("problem_directions", sa.Column("current_problem", sa.Text(), nullable=False, server_default=""))
    op.add_column("problem_directions", sa.Column("baselines", sa.Text(), nullable=False, server_default="[]"))
    op.add_column(
        "problem_directions",
        sa.Column("candidate_mechanism", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "problem_directions",
        sa.Column("success_metrics", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "problem_directions",
        sa.Column("evidence_gaps", sa.Text(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("problem_directions", "evidence_gaps")
    op.drop_column("problem_directions", "success_metrics")
    op.drop_column("problem_directions", "candidate_mechanism")
    op.drop_column("problem_directions", "baselines")
    op.drop_column("problem_directions", "current_problem")
    op.drop_column("problem_directions", "motivation")
    op.drop_table("learning_planning_papers")
    op.drop_column("direction_workshops", "include_graph_context")
    op.drop_column("direction_workshops", "mode")
