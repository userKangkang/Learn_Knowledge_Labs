from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.paper_study import (
    AttachConceptNode, PaperConceptFinalize, PaperConceptItemRead, PaperConceptItemUpdate, PaperConceptMapRead, PaperDocumentRead, PaperSourceTextPreviewRead, PaperTextModelSelect,
    PaperOverviewUpdate, PaperProblemCardCreate, PaperProblemCardRead, PaperProblemCardUpdate, PaperStudyCreate, PaperStudyMessageCreate, PaperStudyRead, PaperStudyUpdate,
)
from app.services.paper_study import PaperStudyService

router = APIRouter(tags=["paper-studies"])
_SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}

@router.get("/graphs/{graph_id}/paper-studies", response_model=list[PaperStudyRead])
def list_studies(graph_id: str, db: Session = Depends(db_session)):
    return PaperStudyService(db).list_studies(graph_id)

@router.post("/graphs/{graph_id}/paper-studies", response_model=PaperStudyRead, status_code=status.HTTP_201_CREATED)
def create_study(graph_id: str, payload: PaperStudyCreate, db: Session = Depends(db_session)):
    return PaperStudyService(db).create_study(graph_id, payload)

@router.get("/paper-studies/{study_id}", response_model=PaperStudyRead)
def get_study(study_id: str, db: Session = Depends(db_session)):
    return PaperStudyService(db).get_study(study_id)

@router.patch("/paper-studies/{study_id}", response_model=PaperStudyRead)
def update_study(study_id: str, payload: PaperStudyUpdate, db: Session = Depends(db_session)):
    return PaperStudyService(db).update_study(study_id, payload)

@router.delete("/paper-studies/{study_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_study(study_id: str, db: Session = Depends(db_session)):
    PaperStudyService(db).delete_study(study_id)
    return Response(status_code=204)

@router.post("/paper-studies/{study_id}/document", response_model=PaperDocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(study_id: str, file: UploadFile = File(...), db: Session = Depends(db_session)):
    return PaperStudyService(db).upload_document(study_id, filename=file.filename or "paper.pdf", content_type=file.content_type or "", data=await file.read())

@router.get("/paper-studies/{study_id}/document/source-text", response_model=PaperSourceTextPreviewRead)
def source_text_preview(study_id: str, db: Session = Depends(db_session)):
    return PaperStudyService(db).source_text_preview(study_id)

@router.post("/paper-studies/{study_id}/document/analyze", response_model=PaperStudyRead)
def analyze_document(study_id: str, db: Session = Depends(db_session)):
    return PaperStudyService(db).analyze_document(study_id)

@router.post("/paper-studies/{study_id}/conversations/{stage}/start", response_model=PaperStudyRead)
def start_conversation(study_id: str, stage: str, text_model: str | None = None, db: Session = Depends(db_session)):
    return PaperStudyService(db).start_conversation(study_id, stage, text_model)

@router.post("/paper-studies/{study_id}/conversations/{stage}/start/stream")
def start_conversation_stream(study_id: str, stage: str, text_model: str | None = None, db: Session = Depends(db_session)):
    service = PaperStudyService(db)
    return StreamingResponse(service.stream_conversation(study_id, stage=stage, text_model=text_model), media_type="text/event-stream", headers=_SSE_HEADERS)

@router.post("/paper-studies/{study_id}/conversations/messages", response_model=PaperStudyRead)
def send_conversation_message(study_id: str, payload: PaperStudyMessageCreate, db: Session = Depends(db_session)):
    return PaperStudyService(db).send_conversation_message(study_id, payload)

@router.post("/paper-studies/{study_id}/conversations/messages/stream")
def send_conversation_message_stream(study_id: str, payload: PaperStudyMessageCreate, db: Session = Depends(db_session)):
    service = PaperStudyService(db)
    return StreamingResponse(service.stream_conversation(study_id, stage=payload.stage, user_content=payload.content, text_model=payload.text_model), media_type="text/event-stream", headers=_SSE_HEADERS)

@router.patch("/paper-studies/{study_id}/overview", response_model=PaperStudyRead)
def update_overview(study_id: str, payload: PaperOverviewUpdate, db: Session = Depends(db_session)):
    return PaperStudyService(db).update_overview(study_id, payload)

@router.post("/paper-studies/{study_id}/problem-cards", response_model=PaperProblemCardRead, status_code=status.HTTP_201_CREATED)
def create_problem_card(study_id: str, payload: PaperProblemCardCreate, db: Session = Depends(db_session)):
    return PaperStudyService(db).create_problem_card(study_id, payload)

@router.patch("/paper-problem-cards/{card_id}", response_model=PaperProblemCardRead)
def update_card(card_id: str, payload: PaperProblemCardUpdate, db: Session = Depends(db_session)):
    return PaperStudyService(db).update_card(card_id, payload)

@router.delete("/paper-problem-cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(card_id: str, db: Session = Depends(db_session)):
    PaperStudyService(db).delete_card(card_id)
    return Response(status_code=204)

@router.get("/paper-problem-cards/{card_id}/concept-map", response_model=PaperConceptMapRead | None)
def get_map(card_id: str, db: Session = Depends(db_session)):
    return PaperStudyService(db).get_concept_map(card_id)

@router.post("/paper-problem-cards/{card_id}/concept-map/generate", response_model=PaperConceptMapRead)
def generate_map(card_id: str, payload: PaperTextModelSelect | None = None, db: Session = Depends(db_session)):
    return PaperStudyService(db).generate_concept_map(card_id, payload.text_model if payload else None)

@router.post("/paper-problem-cards/{card_id}/concept-map/review", response_model=PaperConceptMapRead)
def review_map(card_id: str, payload: PaperTextModelSelect | None = None, db: Session = Depends(db_session)):
    return PaperStudyService(db).review_concept_candidates(card_id, payload.text_model if payload else None)

@router.post("/paper-problem-cards/{card_id}/concept-map/finalize", response_model=PaperConceptMapRead)
def finalize_map(card_id: str, payload: PaperConceptFinalize, db: Session = Depends(db_session)):
    return PaperStudyService(db).finalize_concept_map(card_id, payload)

@router.patch("/paper-concept-items/{item_id}", response_model=PaperConceptItemRead)
def update_item(item_id: str, payload: PaperConceptItemUpdate, db: Session = Depends(db_session)):
    return PaperStudyService(db).update_concept_item(item_id, payload)

@router.post("/paper-concept-items/{item_id}/attach-node", response_model=PaperConceptItemRead)
def attach_node(item_id: str, payload: AttachConceptNode, db: Session = Depends(db_session)):
    return PaperStudyService(db).attach_concept_node(item_id, payload)
