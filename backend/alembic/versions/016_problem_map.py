"""paper-problem map: shared problems, hierarchy edges, card links, positions

Revision ID: 016
Revises: 015
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "016"
down_revision: Union[str, Sequence[str], None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shared_problems",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "graph_id",
            sa.String(length=36),
            sa.ForeignKey("knowledge_graphs.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_shared_problems_graph_id", "shared_problems", ["graph_id"])

    op.create_table(
        "shared_problem_edges",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "graph_id",
            sa.String(length=36),
            sa.ForeignKey("knowledge_graphs.id"),
            nullable=False,
        ),
        sa.Column(
            "source_problem_id",
            sa.String(length=36),
            sa.ForeignKey("shared_problems.id"),
            nullable=False,
        ),
        sa.Column(
            "target_problem_id",
            sa.String(length=36),
            sa.ForeignKey("shared_problems.id"),
            nullable=False,
        ),
        sa.Column("relation_label", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "graph_id",
            "source_problem_id",
            "target_problem_id",
            "relation_label",
            name="uq_shared_problem_edge",
        ),
    )
    op.create_index("ix_shared_problem_edges_graph_id", "shared_problem_edges", ["graph_id"])
    op.create_index(
        "ix_shared_problem_edges_endpoints",
        "shared_problem_edges",
        ["source_problem_id", "target_problem_id"],
    )

    op.create_table(
        "problem_card_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "graph_id",
            sa.String(length=36),
            sa.ForeignKey("knowledge_graphs.id"),
            nullable=False,
        ),
        sa.Column(
            "problem_card_id",
            sa.String(length=36),
            sa.ForeignKey("paper_problem_cards.id"),
            nullable=False,
        ),
        sa.Column(
            "shared_problem_id",
            sa.String(length=36),
            sa.ForeignKey("shared_problems.id"),
            nullable=False,
        ),
        sa.Column("link_type", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "problem_card_id",
            "shared_problem_id",
            name="uq_problem_card_link",
        ),
    )
    op.create_index("ix_problem_card_links_graph_id", "problem_card_links", ["graph_id"])
    op.create_index(
        "ix_problem_card_links_shared_problem_id",
        "problem_card_links",
        ["shared_problem_id"],
    )

    op.create_table(
        "problem_map_positions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "graph_id",
            sa.String(length=36),
            sa.ForeignKey("knowledge_graphs.id"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("position_x", sa.Float(), nullable=False, server_default="0"),
        sa.Column("position_y", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "graph_id",
            "entity_type",
            "entity_id",
            name="uq_problem_map_position",
        ),
    )
    op.create_index("ix_problem_map_positions_graph_id", "problem_map_positions", ["graph_id"])


def downgrade() -> None:
    op.drop_index("ix_problem_map_positions_graph_id", table_name="problem_map_positions")
    op.drop_table("problem_map_positions")
    op.drop_index("ix_problem_card_links_shared_problem_id", table_name="problem_card_links")
    op.drop_index("ix_problem_card_links_graph_id", table_name="problem_card_links")
    op.drop_table("problem_card_links")
    op.drop_index("ix_shared_problem_edges_endpoints", table_name="shared_problem_edges")
    op.drop_index("ix_shared_problem_edges_graph_id", table_name="shared_problem_edges")
    op.drop_table("shared_problem_edges")
    op.drop_index("ix_shared_problems_graph_id", table_name="shared_problems")
    op.drop_table("shared_problems")
