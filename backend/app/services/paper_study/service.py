"""Paper-study service facade.

The full paper-understanding workflow lives in focused sub-services
(documents, conversations, problem cards, concept maps); this class keeps a
single PaperStudyService entry point for API routes and callers.
"""

from app.services.paper_study.base import PaperStudyDeps
from app.services.paper_study.concept_maps import PaperConceptMapService
from app.services.paper_study.conversations import PaperConversationService
from app.services.paper_study.documents import PaperDocumentService
from app.services.paper_study.knowledge_inquiries import PaperKnowledgeInquiryService
from app.services.paper_study.problem_cards import PaperProblemCardService
from app.services.paper_study.studies import PaperStudyCrudService


class PaperStudyService:
    def __init__(self, db) -> None:
        deps = PaperStudyDeps(db)
        self._studies = PaperStudyCrudService(db, deps)
        self._documents = PaperDocumentService(db, deps)
        self._conversations = PaperConversationService(db, deps)
        self._cards = PaperProblemCardService(db, deps)
        self._maps = PaperConceptMapService(db, deps)
        self._knowledge_inquiries = PaperKnowledgeInquiryService(db, deps)

    # --- study CRUD ---
    def list_studies(self, graph_id: str):
        return self._studies.list_studies(graph_id)

    def get_study(self, study_id: str):
        return self._studies.get_study(study_id)

    def create_study(self, graph_id: str, payload):
        return self._studies.create_study(graph_id, payload)

    def update_study(self, study_id: str, payload):
        return self._studies.update_study(study_id, payload)

    def delete_study(self, study_id: str) -> None:
        self._studies.delete_study(study_id)

    # --- document upload / analysis ---
    def upload_document(self, study_id: str, *, filename: str, content_type: str, data: bytes):
        return self._documents.upload_document(study_id, filename=filename, content_type=content_type, data=data)

    def source_text_preview(self, study_id: str):
        return self._documents.source_text_preview(study_id)

    def analyze_document(self, study_id: str):
        return self._documents.analyze_document(study_id)

    # --- conversations ---
    def start_conversation(self, study_id: str, stage: str, text_model: str | None = None):
        return self._conversations.start_conversation(study_id, stage, text_model)

    def send_conversation_message(self, study_id: str, payload):
        return self._conversations.send_conversation_message(study_id, payload)

    def stream_conversation(
        self, study_id: str, *, stage: str, user_content: str | None = None, text_model: str | None = None
    ):
        return self._conversations.stream_conversation(
            study_id, stage=stage, user_content=user_content, text_model=text_model
        )

    def update_overview(self, study_id: str, payload):
        return self._conversations.update_overview(study_id, payload)

    # --- temporary knowledge-point inquiries ---
    def create_knowledge_inquiry(self, study_id: str, payload):
        return self._knowledge_inquiries.create_inquiry(study_id, payload)

    def get_knowledge_inquiry(self, study_id: str, inquiry_id: str):
        return self._knowledge_inquiries.get_inquiry(study_id, inquiry_id)

    def stream_knowledge_inquiry_message(self, study_id: str, inquiry_id: str, payload):
        return self._knowledge_inquiries.stream_message(study_id, inquiry_id, payload)

    def save_knowledge_card(self, study_id: str, inquiry_id: str, payload):
        return self._knowledge_inquiries.save_card(study_id, inquiry_id, payload)

    def discard_knowledge_inquiry(self, study_id: str, inquiry_id: str) -> None:
        self._knowledge_inquiries.discard(study_id, inquiry_id)

    # --- problem cards ---
    def create_problem_card(self, study_id: str, payload):
        return self._cards.create_problem_card(study_id, payload)

    def update_card(self, card_id: str, payload):
        return self._cards.update_card(card_id, payload)

    def delete_card(self, card_id: str) -> None:
        self._cards.delete_card(card_id)

    # --- concept maps ---
    def get_concept_map(self, card_id: str):
        return self._maps.get_concept_map(card_id)

    def generate_concept_map(self, card_id: str, text_model: str | None = None):
        return self._maps.generate_concept_map(card_id, text_model)

    def review_concept_candidates(self, card_id: str, text_model: str | None = None):
        return self._maps.review_concept_candidates(card_id, text_model)

    def finalize_concept_map(self, card_id: str, payload):
        return self._maps.finalize_concept_map(card_id, payload)

    def update_concept_item(self, item_id: str, payload):
        return self._maps.update_concept_item(item_id, payload)

    def attach_concept_node(self, item_id: str, payload):
        return self._maps.attach_concept_node(item_id, payload)
