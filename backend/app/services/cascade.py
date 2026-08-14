from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.paper_study import PaperStudy, PaperStudyDocument
from app.repositories.context_repo import ContextRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.node_repo import NodeRepository
from app.repositories.problem_map_repo import ProblemMapRepository
from app.repositories.session_repo import SessionRepository
from app.repositories.summary_repo import SummaryRepository
from app.services.attachment_service import AttachmentService
from app.services.uploads import safe_remove_upload


def soft_delete_node_content(db: Session, node_id: str) -> None:
    sessions = SessionRepository(db)
    messages = MessageRepository(db)
    summaries = SummaryRepository(db)
    contexts = ContextRepository(db)

    session_ids = sessions.soft_delete_by_node(node_id)
    AttachmentService(db).cleanup_sessions(session_ids)
    contexts.soft_delete_policies_by_sessions(session_ids)
    messages.soft_delete_by_sessions(session_ids)
    summaries.soft_delete_by_node(node_id)


def soft_delete_graph_content(db: Session, graph_id: str) -> None:
    nodes = NodeRepository(db)
    for node in nodes.list_active_by_graph(graph_id):
        soft_delete_node_content(db, node.id)
    studies = db.scalars(select(PaperStudy).where(PaperStudy.graph_id == graph_id)).all()
    for study in studies:
        document = db.scalars(
            select(PaperStudyDocument).where(PaperStudyDocument.study_id == study.id)
        ).first()
        if document:
            safe_remove_upload(document.storage_path, remove_parent=True)
        db.delete(study)

    problem_map = ProblemMapRepository(db)
    for problem in problem_map.list_active_problems(graph_id):
        problem_map.soft_delete_problem(problem)
    for edge in problem_map.list_active_edges(graph_id):
        problem_map.soft_delete_edge(edge)
    for link in problem_map.list_active_links(graph_id):
        problem_map.soft_delete_link(link)
    for position in problem_map.list_positions(graph_id):
        db.delete(position)
    db.flush()
