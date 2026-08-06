"""Editable problem cards produced from the problem-map dialogue."""

from uuid import uuid4

from app.errors import AppError, NotFoundError
from app.models.paper_study import PaperProblemCard
from app.schemas.paper_study import PaperProblemCardCreate, PaperProblemCardRead, PaperProblemCardUpdate
from app.services.paper_study.base import PaperStudyServiceBase


class PaperProblemCardService(PaperStudyServiceBase):
    def create_problem_card(self, study_id: str, payload: PaperProblemCardCreate) -> PaperProblemCardRead:
        study = self._require_study(study_id)
        overview = self.repo.get_overview(study.id)
        if not overview or overview.user_status != "CONFIRMED":
            raise AppError("OVERVIEW_CONFIRM_REQUIRED", "请先确认暂定理解", status_code=400)
        dialogue = self.repo.list_messages(study.id, "PROBLEM_MAP")
        if not any(item.role == "USER" for item in dialogue):
            raise AppError("PROBLEM_MAP_DIALOGUE_REQUIRED", "请先与 AI 讨论论文有哪些问题，再手动填写问题卡", status_code=400)
        card = PaperProblemCard(
            id=str(uuid4()), study_id=study.id, title=payload.title.strip(),
            qualitative_overview=payload.qualitative_overview.strip(), technical_interpretation=payload.technical_interpretation.strip(),
            paper_claims=[item.strip() for item in payload.paper_claims if item.strip()],
            paper_not_said=[item.strip() for item in payload.paper_not_said if item.strip()],
            verification_anchor=payload.verification_anchor.strip(), verification_prompt=payload.verification_prompt.strip(),
            order_index=len(self.repo.list_cards(study.id)),
        )
        self.repo.add(card)
        study.status = "PROBLEM_MAP"
        self.db.commit()
        self.db.refresh(card)
        return self._card_read(card)

    def update_card(self, card_id: str, payload: PaperProblemCardUpdate) -> PaperProblemCardRead:
        card = self.repo.get_card(card_id)
        if not card:
            raise NotFoundError("PAPER_PROBLEM_NOT_FOUND", "问题卡不存在")
        for field, value in payload.model_dump(exclude_none=True).items():
            if isinstance(value, str):
                value = value.strip()
            setattr(card, field, value)
        self.db.commit()
        self.db.refresh(card)
        return self._card_read(card)

    def delete_card(self, card_id: str) -> None:
        card = self.repo.get_card(card_id)
        if not card:
            raise NotFoundError("PAPER_PROBLEM_NOT_FOUND", "问题卡不存在")
        self.db.delete(card)
        self.db.commit()
