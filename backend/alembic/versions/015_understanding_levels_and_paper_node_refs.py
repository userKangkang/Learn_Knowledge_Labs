"""add progressive understanding levels to graph nodes and concept items

Revision ID: 015
Revises: 014
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "015"
down_revision: Union[str, Sequence[str], None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_nodes",
        sa.Column("understanding_level", sa.String(length=24), nullable=False, server_default="NEEDS_WORK"),
    )
    op.execute("UPDATE paper_concept_items SET user_status = 'DEEP' WHERE user_status = 'UNDERSTOOD'")
    op.execute("UPDATE paper_concept_items SET user_status = 'NEEDS_WORK' WHERE user_status IN ('PENDING', 'NEEDS_WORK')")


def downgrade() -> None:
    op.execute("UPDATE paper_concept_items SET user_status = 'UNDERSTOOD' WHERE user_status = 'DEEP'")
    op.execute("UPDATE paper_concept_items SET user_status = 'PENDING' WHERE user_status IN ('BASIC', 'NEEDS_WORK')")
    op.drop_column("knowledge_nodes", "understanding_level")
