"""CRUD for paper-understanding records (the top-level aggregate)."""

from uuid import uuid4

from app.models.paper_study import PaperStudy, PaperStudyOverview
from app.schemas.paper_study import PaperStudyCreate, PaperStudyRead, PaperStudyUpdate
from app.services.paper_study.base import PaperStudyServiceBase
from app.services.uploads import safe_remove_upload


class PaperStudyCrudService(PaperStudyServiceBase):
    def list_studies(self, graph_id: str) -> list[PaperStudyRead]:
        self._require_graph(graph_id)
        return [self._study_read(item) for item in self.repo.list_studies(graph_id)]

    def get_study(self, study_id: str) -> PaperStudyRead:
        return self._study_read(self._require_study(study_id))

    def create_study(self, graph_id: str, payload: PaperStudyCreate) -> PaperStudyRead:
        self._require_graph(graph_id)
        study = PaperStudy(id=str(uuid4()), graph_id=graph_id, title=payload.title.strip())
        self.repo.add(study)
        self.repo.add(PaperStudyOverview(study_id=study.id))
        self.db.commit()
        self.db.refresh(study)
        return self._study_read(study)

    def update_study(self, study_id: str, payload: PaperStudyUpdate) -> PaperStudyRead:
        study = self._require_study(study_id)
        study.title = payload.title.strip()
        self.db.commit()
        self.db.refresh(study)
        return self._study_read(study)

    def delete_study(self, study_id: str) -> None:
        study = self._require_study(study_id)
        document = self.repo.get_document(study.id)
        if document:
            safe_remove_upload(document.storage_path, remove_parent=True)
        self.db.delete(study)
        self.db.commit()
