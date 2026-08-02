"""conversation side branches for temp ask

Revision ID: 007
Revises: 006
Create Date: 2026-08-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, Sequence[str], None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "conversation_branches" not in tables:
        op.create_table(
            "conversation_branches",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("session_id", sa.String(length=36), sa.ForeignKey("conversation_sessions.id"), nullable=False),
            sa.Column("anchor_message_id", sa.String(length=36), sa.ForeignKey("chat_messages.id"), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_conversation_branches_session_id", "conversation_branches", ["session_id"])
        op.create_index("ix_conversation_branches_anchor_message_id", "conversation_branches", ["anchor_message_id"])

    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("chat_messages")}
    if "branch_id" not in cols:
        with op.batch_alter_table("chat_messages") as batch:
            batch.add_column(sa.Column("branch_id", sa.String(length=36), nullable=True))
            batch.create_foreign_key(
                "fk_chat_messages_branch_id",
                "conversation_branches",
                ["branch_id"],
                ["id"],
            )
        op.create_index("ix_chat_messages_branch_id", "chat_messages", ["branch_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_branch_id", table_name="chat_messages")
    with op.batch_alter_table("chat_messages") as batch:
        batch.drop_constraint("fk_chat_messages_branch_id", type_="foreignkey")
        batch.drop_column("branch_id")
    op.drop_index("ix_conversation_branches_anchor_message_id", table_name="conversation_branches")
    op.drop_index("ix_conversation_branches_session_id", table_name="conversation_branches")
    op.drop_table("conversation_branches")
