from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.paper_study import (
    PaperConceptItem,
    PaperConceptMap,
    PaperConceptRelation,
    PaperProblemCard,
    PaperStudy,
    PaperStudyDocument,
    PaperStudyMessage,
    PaperStudyOverview,
    PaperKnowledgeInquiry,
    PaperKnowledgeInquiryMessage,
)


class PaperStudyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, entity):
        self.db.add(entity)
        self.db.flush()
        return entity

    def get_study(self, study_id: str) -> PaperStudy | None:
        return self.db.get(PaperStudy, study_id)

    def list_studies(self, graph_id: str) -> list[PaperStudy]:
        return list(self.db.scalars(select(PaperStudy).where(PaperStudy.graph_id == graph_id).order_by(PaperStudy.updated_at.desc())).all())

    def get_document(self, study_id: str) -> PaperStudyDocument | None:
        return self.db.scalars(select(PaperStudyDocument).where(PaperStudyDocument.study_id == study_id)).first()

    def get_overview(self, study_id: str) -> PaperStudyOverview | None:
        return self.db.get(PaperStudyOverview, study_id)

    def list_messages(self, study_id: str, stage: str | None = None) -> list[PaperStudyMessage]:
        stmt = select(PaperStudyMessage).where(PaperStudyMessage.study_id == study_id)
        if stage:
            stmt = stmt.where(PaperStudyMessage.stage == stage)
        return list(self.db.scalars(stmt.order_by(PaperStudyMessage.stage, PaperStudyMessage.sequence_index)).all())

    def next_message_index(self, study_id: str, stage: str) -> int:
        from sqlalchemy import func
        value = self.db.scalar(select(func.max(PaperStudyMessage.sequence_index)).where(PaperStudyMessage.study_id == study_id, PaperStudyMessage.stage == stage))
        return int(value or 0) + 1

    def get_knowledge_inquiry(self, inquiry_id: str) -> PaperKnowledgeInquiry | None:
        return self.db.get(PaperKnowledgeInquiry, inquiry_id)

    def list_knowledge_inquiries(self, study_id: str) -> list[PaperKnowledgeInquiry]:
        return list(self.db.scalars(
            select(PaperKnowledgeInquiry)
            .where(PaperKnowledgeInquiry.study_id == study_id)
            .order_by(PaperKnowledgeInquiry.created_at.desc())
        ).all())

    def list_knowledge_inquiry_messages(self, inquiry_id: str) -> list[PaperKnowledgeInquiryMessage]:
        return list(self.db.scalars(
            select(PaperKnowledgeInquiryMessage)
            .where(PaperKnowledgeInquiryMessage.inquiry_id == inquiry_id)
            .order_by(PaperKnowledgeInquiryMessage.sequence_index)
        ).all())

    def next_knowledge_inquiry_message_index(self, inquiry_id: str) -> int:
        from sqlalchemy import func
        value = self.db.scalar(select(func.max(PaperKnowledgeInquiryMessage.sequence_index)).where(PaperKnowledgeInquiryMessage.inquiry_id == inquiry_id))
        return int(value or 0) + 1

    def list_cards(self, study_id: str) -> list[PaperProblemCard]:
        return list(self.db.scalars(select(PaperProblemCard).where(PaperProblemCard.study_id == study_id).order_by(PaperProblemCard.order_index)).all())

    def get_card(self, card_id: str) -> PaperProblemCard | None:
        return self.db.get(PaperProblemCard, card_id)

    def get_concept_map(self, card_id: str) -> PaperConceptMap | None:
        return self.db.scalars(select(PaperConceptMap).where(PaperConceptMap.problem_card_id == card_id)).first()

    def get_concept_item(self, item_id: str) -> PaperConceptItem | None:
        return self.db.get(PaperConceptItem, item_id)

    def list_concept_items(self, map_id: str) -> list[PaperConceptItem]:
        return list(self.db.scalars(select(PaperConceptItem).where(PaperConceptItem.concept_map_id == map_id).order_by(PaperConceptItem.order_index)).all())

    def list_relations(self, map_id: str) -> list[PaperConceptRelation]:
        return list(self.db.scalars(select(PaperConceptRelation).where(PaperConceptRelation.concept_map_id == map_id)).all())
