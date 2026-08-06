from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.node import NodeCreate, NodePaperReferenceCreate, NodePositionUpdate, NodeRead, NodeUpdate
from app.services.node_service import NodeService

router = APIRouter(tags=["nodes"])


@router.get("/graphs/{graph_id}/nodes", response_model=list[NodeRead])
def list_nodes(graph_id: str, db: Session = Depends(db_session)) -> list[NodeRead]:
    return NodeService(db).list_nodes(graph_id)


@router.post("/graphs/{graph_id}/nodes", response_model=NodeRead, status_code=status.HTTP_201_CREATED)
def create_node(graph_id: str, payload: NodeCreate, db: Session = Depends(db_session)) -> NodeRead:
    return NodeService(db).create_node(graph_id, payload)


@router.get("/nodes/{node_id}", response_model=NodeRead)
def get_node(node_id: str, db: Session = Depends(db_session)) -> NodeRead:
    return NodeService(db).get_node(node_id)


@router.patch("/nodes/{node_id}", response_model=NodeRead)
def update_node(node_id: str, payload: NodeUpdate, db: Session = Depends(db_session)) -> NodeRead:
    return NodeService(db).update_node(node_id, payload)


@router.post("/nodes/{node_id}/paper-references", response_model=NodeRead)
def add_paper_reference(node_id: str, payload: NodePaperReferenceCreate, db: Session = Depends(db_session)) -> NodeRead:
    return NodeService(db).add_paper_reference(node_id, payload)


@router.patch("/nodes/{node_id}/position", response_model=NodeRead)
def update_node_position(
    node_id: str,
    payload: NodePositionUpdate,
    db: Session = Depends(db_session),
) -> NodeRead:
    return NodeService(db).update_position(node_id, payload)


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(node_id: str, db: Session = Depends(db_session)) -> Response:
    NodeService(db).delete_node(node_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
