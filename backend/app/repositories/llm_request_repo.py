from sqlalchemy.orm import Session

from app.models.llm_request import LLMRequest


class LLMRequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, request_id: str) -> LLMRequest | None:
        return self.db.get(LLMRequest, request_id)

    def add(self, request: LLMRequest) -> LLMRequest:
        self.db.add(request)
        self.db.flush()
        return request
