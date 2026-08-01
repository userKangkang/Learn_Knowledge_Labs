from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.edge import EdgeCreate, EdgeRead, EdgeUpdate
from app.services.edge_service import EdgeService

router = APIRouter(tags=["edges"])


@router.get("/graphs/{graph_id}/edges", response_model=list[EdgeRead])
def list_edges(graph_id: str, db: Session = Depends(db_session)) -> list[EdgeRead]:
    return EdgeService(db).list_edges(graph_id)


@router.post("/graphs/{graph_id}/edges", response_model=EdgeRead, status_code=status.HTTP_201_CREATED)
def create_edge(graph_id: str, payload: EdgeCreate, db: Session = Depends(db_session)) -> EdgeRead:
    return EdgeService(db).create_edge(graph_id, payload)


@router.patch("/edges/{edge_id}", response_model=EdgeRead)
def update_edge(edge_id: str, payload: EdgeUpdate, db: Session = Depends(db_session)) -> EdgeRead:
    return EdgeService(db).update_edge(edge_id, payload)


@router.delete("/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_edge(edge_id: str, db: Session = Depends(db_session)) -> Response:
    EdgeService(db).delete_edge(edge_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
