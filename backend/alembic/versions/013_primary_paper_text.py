"""use extracted paper text as primary evidence

Revision ID: 013
Revises: 012
Create Date: 2026-08-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, Sequence[str], None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("paper_study_documents", sa.Column("kimi_detailed_analysis", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("paper_study_documents", "kimi_detailed_analysis")
