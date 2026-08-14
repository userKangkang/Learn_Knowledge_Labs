"""replace learning planning with paper understanding loop

Revision ID: 011
Revises: 010
Create Date: 2026-08-03
"""

from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, Sequence[str], None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These are the complete old planning-domain tables.  They are intentionally
    # dropped before the new bounded paper-understanding loop is introduced.
    # Old paper uploads were stored only below uploads/learning-planning.  Use
    # the exact DB paths and a containment check; no other attachment directory
    # is inspected or modified.
    old_paths = op.get_bind().execute(sa.text("SELECT storage_path FROM learning_planning_papers")).scalars()
    old_upload_root = (Path(__file__).resolve().parents[2] / "data" / "uploads" / "learning-planning").resolve()
    for raw_path in old_paths:
        try:
            path = Path(str(raw_path)).resolve()
            if path.is_relative_to(old_upload_root):
                path.unlink(missing_ok=True)
        except OSError:
            # Schema migration must remain usable if an old file has already
            # been removed manually; the registered data is still discarded.
            pass

    op.drop_table("learning_route_edges")
    op.drop_table("learning_route_nodes")
    op.drop_table("learning_route_stages")
    op.drop_table("learning_routes")
    op.drop_table("learning_planning_papers")
    op.drop_table("problem_directions")
    op.drop_table("direction_workshop_messages")
    op.drop_table("direction_workshops")

    op.create_table(
        "paper_studies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("graph_id", sa.String(length=36), sa.ForeignKey("knowledge_graphs.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="OVERVIEW"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("ix_paper_studies_graph_id", "paper_studies", ["graph_id"])
    op.create_table(
        "paper_study_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("study_id", sa.String(length=36), sa.ForeignKey("paper_studies.id"), nullable=False, unique=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("extracted_text", sa.Text()),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="UPLOADED"), sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("ix_paper_study_documents_study_id", "paper_study_documents", ["study_id"], unique=True)
    op.create_table(
        "paper_study_overviews",
        sa.Column("study_id", sa.String(length=36), sa.ForeignKey("paper_studies.id"), primary_key=True),
        sa.Column("research_context", sa.Text(), nullable=False, server_default=""), sa.Column("core_problem", sa.Text(), nullable=False, server_default=""),
        sa.Column("main_approach", sa.Text(), nullable=False, server_default=""), sa.Column("claimed_effect", sa.Text(), nullable=False, server_default=""),
        sa.Column("user_understanding", sa.Text(), nullable=False, server_default=""), sa.Column("user_status", sa.String(length=24), nullable=False, server_default="DRAFT"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_table(
        "paper_problem_cards",
        sa.Column("id", sa.String(length=36), primary_key=True), sa.Column("study_id", sa.String(length=36), sa.ForeignKey("paper_studies.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False), sa.Column("qualitative_overview", sa.Text(), nullable=False, server_default=""), sa.Column("technical_interpretation", sa.Text(), nullable=False, server_default=""),
        sa.Column("paper_claims", sa.JSON(), nullable=False, server_default=sa.text("'[]'")), sa.Column("paper_not_said", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("user_interest", sa.Text(), nullable=False, server_default=""), sa.Column("user_stuck_point", sa.Text(), nullable=False, server_default=""),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("status", sa.String(length=24), nullable=False, server_default="UNOPENED"),
        sa.Column("verification_anchor", sa.Text(), nullable=False, server_default=""), sa.Column("verification_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("verification_answer", sa.Text(), nullable=False, server_default=""), sa.Column("verification_status", sa.String(length=24), nullable=False, server_default="PENDING"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("ix_paper_problem_cards_study_id", "paper_problem_cards", ["study_id"])
    op.create_table(
        "paper_concept_maps",
        sa.Column("id", sa.String(length=36), primary_key=True), sa.Column("problem_card_id", sa.String(length=36), sa.ForeignKey("paper_problem_cards.id"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("ix_paper_concept_maps_problem_card_id", "paper_concept_maps", ["problem_card_id"], unique=True)
    op.create_table(
        "paper_concept_items",
        sa.Column("id", sa.String(length=36), primary_key=True), sa.Column("concept_map_id", sa.String(length=36), sa.ForeignKey("paper_concept_maps.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False), sa.Column("explanation", sa.Text(), nullable=False, server_default=""), sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("paper_anchor", sa.Text(), nullable=False, server_default=""), sa.Column("graph_node_id", sa.String(length=36), sa.ForeignKey("knowledge_nodes.id")),
        sa.Column("user_status", sa.String(length=24), nullable=False, server_default="NEEDS_WORK"), sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_paper_concept_items_concept_map_id", "paper_concept_items", ["concept_map_id"])
    op.create_table(
        "paper_concept_relations",
        sa.Column("id", sa.String(length=36), primary_key=True), sa.Column("concept_map_id", sa.String(length=36), sa.ForeignKey("paper_concept_maps.id"), nullable=False),
        sa.Column("source_item_id", sa.String(length=36), sa.ForeignKey("paper_concept_items.id"), nullable=False), sa.Column("target_item_id", sa.String(length=36), sa.ForeignKey("paper_concept_items.id"), nullable=False), sa.Column("relation_label", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("concept_map_id", "source_item_id", "target_item_id", name="uq_paper_concept_relation"),
    )
    op.create_index("ix_paper_concept_relations_concept_map_id", "paper_concept_relations", ["concept_map_id"])
    op.create_table(
        "knowledge_node_paper_references",
        sa.Column("id", sa.String(length=36), primary_key=True), sa.Column("node_id", sa.String(length=36), sa.ForeignKey("knowledge_nodes.id"), nullable=False), sa.Column("document_id", sa.String(length=36), sa.ForeignKey("paper_study_documents.id"), nullable=False),
        sa.Column("location", sa.String(length=512), nullable=False, server_default=""), sa.Column("link_type", sa.String(length=32), nullable=False, server_default="MECHANISM"), sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("ix_knowledge_node_paper_references_node_id", "knowledge_node_paper_references", ["node_id"])
    op.create_index("ix_knowledge_node_paper_references_document_id", "knowledge_node_paper_references", ["document_id"])


def downgrade() -> None:
    raise NotImplementedError("旧的学习规划数据已按产品决定清理，不能恢复")
