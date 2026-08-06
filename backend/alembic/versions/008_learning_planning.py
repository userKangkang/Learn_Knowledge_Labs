"""problem directions and learning routes

Revision ID: 008
Revises: 007
Create Date: 2026-08-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, Sequence[str], None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "direction_workshops",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("graph_id", sa.String(length=36), sa.ForeignKey("knowledge_graphs.id"), nullable=False),
        sa.Column("root_node_id", sa.String(length=36), sa.ForeignKey("knowledge_nodes.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("selected_session_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_direction_workshops_graph_id", "direction_workshops", ["graph_id"])

    op.create_table(
        "direction_workshop_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workshop_id", sa.String(length=36), sa.ForeignKey("direction_workshops.id"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
    )
    op.create_index(
        "ix_direction_workshop_messages_workshop_id", "direction_workshop_messages", ["workshop_id"]
    )

    op.create_table(
        "problem_directions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("graph_id", sa.String(length=36), sa.ForeignKey("knowledge_graphs.id"), nullable=False),
        sa.Column("workshop_id", sa.String(length=36), sa.ForeignKey("direction_workshops.id"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("real_scenario", sa.Text(), nullable=False),
        sa.Column("central_question", sa.Text(), nullable=False),
        sa.Column("key_tension", sa.Text(), nullable=False),
        sa.Column("outcome_task", sa.Text(), nullable=False),
        sa.Column("required_foundations", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("out_of_scope", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="MANUAL"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_problem_directions_graph_id", "problem_directions", ["graph_id"])
    op.create_index("ix_problem_directions_workshop_id", "problem_directions", ["workshop_id"])

    op.create_table(
        "learning_routes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("direction_id", sa.String(length=36), sa.ForeignKey("problem_directions.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_learning_routes_direction_id", "learning_routes", ["direction_id"])

    op.create_table(
        "learning_route_stages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("route_id", sa.String(length=36), sa.ForeignKey("learning_routes.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.UniqueConstraint("route_id", "order_index", name="uq_learning_route_stage_order"),
    )
    op.create_index("ix_learning_route_stages_route_id", "learning_route_stages", ["route_id"])

    op.create_table(
        "learning_route_nodes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("route_id", sa.String(length=36), sa.ForeignKey("learning_routes.id"), nullable=False),
        sa.Column("stage_id", sa.String(length=36), sa.ForeignKey("learning_route_stages.id"), nullable=False),
        sa.Column("node_key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("pedagogical_role", sa.String(length=32), nullable=False),
        sa.Column("why_now", sa.Text(), nullable=False),
        sa.Column("completion_criterion", sa.Text(), nullable=False),
        sa.Column("is_main_path", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.UniqueConstraint("route_id", "node_key", name="uq_learning_route_node_key"),
    )
    op.create_index("ix_learning_route_nodes_route_id", "learning_route_nodes", ["route_id"])
    op.create_index("ix_learning_route_nodes_stage_id", "learning_route_nodes", ["stage_id"])

    op.create_table(
        "learning_route_edges",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("route_id", sa.String(length=36), sa.ForeignKey("learning_routes.id"), nullable=False),
        sa.Column("source_node_id", sa.String(length=36), sa.ForeignKey("learning_route_nodes.id"), nullable=False),
        sa.Column("target_node_id", sa.String(length=36), sa.ForeignKey("learning_route_nodes.id"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="MAIN"),
        sa.UniqueConstraint("route_id", "source_node_id", "target_node_id", name="uq_learning_route_edge"),
    )
    op.create_index("ix_learning_route_edges_route_id", "learning_route_edges", ["route_id"])
    op.create_index("ix_learning_route_edges_source_node_id", "learning_route_edges", ["source_node_id"])
    op.create_index("ix_learning_route_edges_target_node_id", "learning_route_edges", ["target_node_id"])


def downgrade() -> None:
    op.drop_table("learning_route_edges")
    op.drop_table("learning_route_nodes")
    op.drop_table("learning_route_stages")
    op.drop_table("learning_routes")
    op.drop_table("problem_directions")
    op.drop_table("direction_workshop_messages")
    op.drop_table("direction_workshops")
