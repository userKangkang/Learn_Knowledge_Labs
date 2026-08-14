from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.problem_map import (
    ProblemCardLinkCreate,
    ProblemCardLinkRead,
    ProblemCardLinkUpdate,
    ProblemMapApplyRequest,
    ProblemMapApplyResult,
    ProblemMapBundleRead,
    ProblemMapPositionItem,
    ProblemMapPositionRead,
    ProblemMapSuggestResponse,
    RelatedPaperSearchRequest,
    SharedProblemEdgeCreate,
    SharedProblemEdgeRead,
    SharedProblemEdgeUpdate,
    SharedProblemCreate,
    SharedProblemUpdate,
    SharedProblemWithCoverage,
)
from app.services.problem_map_suggest import ProblemMapSuggestService
from app.services.problem_map_service import ProblemMapService
from app.services.related_paper_search import RelatedPaperSearchService

router = APIRouter(tags=["problem-map"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.get("/graphs/{graph_id}/problem-map", response_model=ProblemMapBundleRead)
def get_problem_map(graph_id: str, db: Session = Depends(db_session)) -> dict:
    return ProblemMapService(db).get_problem_map(graph_id)


@router.get("/graphs/{graph_id}/problems", response_model=list[SharedProblemWithCoverage])
def list_problems(graph_id: str, db: Session = Depends(db_session)) -> list[dict]:
    return ProblemMapService(db).list_problems(graph_id)


@router.post(
    "/graphs/{graph_id}/problems",
    response_model=SharedProblemWithCoverage,
    status_code=status.HTTP_201_CREATED,
)
def create_problem(graph_id: str, payload: SharedProblemCreate, db: Session = Depends(db_session)) -> dict:
    return ProblemMapService(db).create_problem(graph_id, payload)


@router.get("/problems/{problem_id}", response_model=SharedProblemWithCoverage)
def get_problem(problem_id: str, db: Session = Depends(db_session)) -> dict:
    return ProblemMapService(db).get_problem(problem_id)


@router.patch("/problems/{problem_id}", response_model=SharedProblemWithCoverage)
def update_problem(problem_id: str, payload: SharedProblemUpdate, db: Session = Depends(db_session)) -> dict:
    return ProblemMapService(db).update_problem(problem_id, payload)


@router.delete("/problems/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_problem(problem_id: str, db: Session = Depends(db_session)) -> Response:
    ProblemMapService(db).delete_problem(problem_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/graphs/{graph_id}/problem-edges", response_model=list[SharedProblemEdgeRead])
def list_problem_edges(graph_id: str, db: Session = Depends(db_session)) -> list:
    return ProblemMapService(db).list_edges(graph_id)


@router.post(
    "/graphs/{graph_id}/problem-edges",
    response_model=SharedProblemEdgeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_problem_edge(graph_id: str, payload: SharedProblemEdgeCreate, db: Session = Depends(db_session)):
    return ProblemMapService(db).create_edge(graph_id, payload)


@router.patch("/problem-edges/{edge_id}", response_model=SharedProblemEdgeRead)
def update_problem_edge(edge_id: str, payload: SharedProblemEdgeUpdate, db: Session = Depends(db_session)):
    return ProblemMapService(db).update_edge(edge_id, payload)


@router.delete("/problem-edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_problem_edge(edge_id: str, db: Session = Depends(db_session)) -> Response:
    ProblemMapService(db).delete_edge(edge_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/graphs/{graph_id}/card-links", response_model=list[ProblemCardLinkRead])
def list_card_links(graph_id: str, db: Session = Depends(db_session)) -> list:
    return ProblemMapService(db).list_links(graph_id)


@router.post(
    "/problem-cards/{card_id}/links",
    response_model=ProblemCardLinkRead,
    status_code=status.HTTP_201_CREATED,
)
def create_card_link(card_id: str, payload: ProblemCardLinkCreate, db: Session = Depends(db_session)):
    return ProblemMapService(db).create_link(card_id, payload)


@router.patch("/card-links/{link_id}", response_model=ProblemCardLinkRead)
def update_card_link(link_id: str, payload: ProblemCardLinkUpdate, db: Session = Depends(db_session)):
    return ProblemMapService(db).update_link(link_id, payload)


@router.delete("/card-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card_link(link_id: str, db: Session = Depends(db_session)) -> Response:
    ProblemMapService(db).delete_link(link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/graphs/{graph_id}/problem-map/positions",
    response_model=list[ProblemMapPositionRead],
)
def save_positions(
    graph_id: str,
    payload: list[ProblemMapPositionItem],
    db: Session = Depends(db_session),
) -> list:
    return ProblemMapService(db).save_positions(graph_id, payload)


@router.post("/graphs/{graph_id}/problem-map/suggest", response_model=ProblemMapSuggestResponse)
def suggest_problem_map(graph_id: str, db: Session = Depends(db_session)) -> ProblemMapSuggestResponse:
    return ProblemMapSuggestService(db).suggest(graph_id)


@router.post("/graphs/{graph_id}/problem-map/apply", response_model=ProblemMapApplyResult)
def apply_problem_map(
    graph_id: str,
    payload: ProblemMapApplyRequest,
    db: Session = Depends(db_session),
) -> ProblemMapApplyResult:
    return ProblemMapSuggestService(db).apply(graph_id, payload)


@router.post("/graphs/{graph_id}/problem-map/related-paper-search/stream")
def stream_related_paper_search(
    graph_id: str,
    payload: RelatedPaperSearchRequest,
    db: Session = Depends(db_session),
) -> StreamingResponse:
    service = RelatedPaperSearchService(db)
    prepared = service.prepare(graph_id, payload)
    return StreamingResponse(service.stream(prepared), media_type="text/event-stream", headers=_SSE_HEADERS)
