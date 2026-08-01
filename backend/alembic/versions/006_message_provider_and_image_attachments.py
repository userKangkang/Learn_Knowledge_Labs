"""message provider and image attachment support

Revision ID: 006
Revises: 005
Create Date: 2026-07-31

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, Sequence[str], None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch:
        batch.add_column(sa.Column("provider", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("vendor_meta", sa.Text(), nullable=True))
    with op.batch_alter_table("message_attachments") as batch:
        batch.add_column(sa.Column("kind", sa.String(length=32), nullable=False, server_default="pdf"))


def downgrade() -> None:
    with op.batch_alter_table("message_attachments") as batch:
        batch.drop_column("kind")
    with op.batch_alter_table("chat_messages") as batch:
        batch.drop_column("vendor_meta")
        batch.drop_column("provider")
