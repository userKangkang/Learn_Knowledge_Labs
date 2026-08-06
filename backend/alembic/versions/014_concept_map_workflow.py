"""persist the three-step concept map workflow

Revision ID: 014
Revises: 013
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, Sequence[str], None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("paper_concept_maps", sa.Column("workflow_stage", sa.String(length=24), nullable=False, server_default="EMPTY"))
    op.add_column("paper_concept_maps", sa.Column("landscape_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("paper_concept_maps", sa.Column("candidate_review_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("paper_concept_maps", sa.Column("confirmed_candidate_keys_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    op.drop_column("paper_concept_maps", "confirmed_candidate_keys_json")
    op.drop_column("paper_concept_maps", "candidate_review_json")
    op.drop_column("paper_concept_maps", "landscape_json")
    op.drop_column("paper_concept_maps", "workflow_stage")
