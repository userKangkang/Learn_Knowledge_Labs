from sqlalchemy.orm import Session

from app.repositories.context_repo import ContextRepository
from app.models.paper_study import PaperStudy
from app.repositories.message_repo import MessageRepository
from app.repositories.node_repo import NodeRepository
from app.repositories.session_repo import SessionRepository
from app.repositories.summary_repo import SummaryRepository


def soft_delete_node_content(db: Session, node_id: str) -> None:
    sessions = SessionRepository(db)
    messages = MessageRepository(db)
    summaries = SummaryRepository(db)
    contexts = ContextRepository(db)

    session_ids = sessions.soft_delete_by_node(node_id)
    contexts.soft_delete_policies_by_sessions(session_ids)
    messages.soft_delete_by_sessions(session_ids)
    summaries.soft_delete_by_node(node_id)


def soft_delete_graph_content(db: Session, graph_id: str) -> None:
    nodes = NodeRepository(db)
    for node in nodes.list_active_by_graph(graph_id):
        soft_delete_node_content(db, node.id)
    for study in db.query(PaperStudy).filter(PaperStudy.graph_id == graph_id).all():
        db.delete(study)
    db.flush()
