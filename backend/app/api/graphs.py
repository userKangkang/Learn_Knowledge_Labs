from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.graph import GraphCreate, GraphRead, GraphUpdate
from app.services.graph_service import GraphService

router = APIRouter(prefix="/graphs", tags=["graphs"])


@router.get("", response_model=list[GraphRead])
def list_graphs(db: Session = Depends(db_session)) -> list[GraphRead]:
    return GraphService(db).list_graphs()


@router.post("", response_model=GraphRead, status_code=status.HTTP_201_CREATED)
def create_graph(payload: GraphCreate, db: Session = Depends(db_session)) -> GraphRead:
    return GraphService(db).create_graph(payload)


@router.get("/{graph_id}", response_model=GraphRead)
def get_graph(graph_id: str, db: Session = Depends(db_session)) -> GraphRead:
    return GraphService(db).get_graph(graph_id)


@router.patch("/{graph_id}", response_model=GraphRead)
def update_graph(graph_id: str, payload: GraphUpdate, db: Session = Depends(db_session)) -> GraphRead:
    return GraphService(db).update_graph(graph_id, payload)


@router.delete("/{graph_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_graph(graph_id: str, db: Session = Depends(db_session)) -> Response:
    GraphService(db).delete_graph(graph_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
