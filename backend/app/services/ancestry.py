from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.edge import KnowledgeEdge
from app.models.node import KnowledgeNode


def _active_edges_into(db: Session, graph_id: str) -> dict[str, list[str]]:
    """Map target_node_id -> list of source_node_id (parents)."""
    stmt = select(KnowledgeEdge).where(
        KnowledgeEdge.graph_id == graph_id,
        KnowledgeEdge.deleted_at.is_(None),
    )
    parents: dict[str, list[str]] = {}
    for edge in db.scalars(stmt).all():
        parents.setdefault(edge.target_node_id, []).append(edge.source_node_id)
    return parents


def ancestor_generations(db: Session, node_id: str, graph_id: str, max_gen: int = 3) -> dict[str, int]:
    """Return {ancestor_node_id: generation} for generations 1..max_gen. Closest gen wins if multi-path."""
    parents_map = _active_edges_into(db, graph_id)
    result: dict[str, int] = {}
    frontier = {node_id}
    for gen in range(1, max_gen + 1):
        next_frontier: set[str] = set()
        for current in frontier:
            for parent_id in parents_map.get(current, []):
                if parent_id == node_id:
                    continue
                if parent_id not in result:
                    result[parent_id] = gen
                    next_frontier.add(parent_id)
        frontier = next_frontier
        if not frontier:
            break
    return result


def classify_source_node(
    db: Session,
    current_node_id: str,
    source_node_id: str,
    graph_id: str,
) -> str:
    """Return SAME_NODE | ANCESTOR | NON_ANCESTOR."""
    if source_node_id == current_node_id:
        return "SAME_NODE"
    ancestors = ancestor_generations(db, current_node_id, graph_id, max_gen=3)
    if source_node_id in ancestors:
        return "ANCESTOR"
    source = db.scalars(
        select(KnowledgeNode).where(
            KnowledgeNode.id == source_node_id,
            KnowledgeNode.deleted_at.is_(None),
            KnowledgeNode.graph_id == graph_id,
        )
    ).first()
    if not source:
        raise ValueError("SOURCE_NODE_NOT_FOUND")
    return "NON_ANCESTOR"
