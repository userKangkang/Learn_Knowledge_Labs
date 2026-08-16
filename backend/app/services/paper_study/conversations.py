"""Overview / problem-map conversations and the editable provisional-understanding overview."""

import json
from collections.abc import Iterator
from uuid import uuid4

from app.errors import AppError, NotFoundError
from app.models.paper_study import PaperStudy, PaperStudyMessage
from app.schemas.paper_study import PaperOverviewUpdate, PaperStudyMessageCreate, PaperStudyRead
from app.services.paper_study.base import PaperStudyServiceBase
from app.services.paper_study.prompts import OVERVIEW_CONVERSATION_PROMPT, PROBLEM_MAP_CONVERSATION_PROMPT
from app.services.sse import sse_event


class PaperConversationService(PaperStudyServiceBase):
    def _conversation_context(self, study: PaperStudy, stage: str) -> list[dict]:
        document = self._require_paper_material(study)
        overview = self.repo.get_overview(study.id)
        context: dict[str, object] = {}
        if (document.extracted_text or "").strip():
            context["primary_paper_text"] = document.extracted_text
            context["primary_paper_text_note"] = "这是从用户 PDF 提取的原文文本，是事实判断的优先依据。"
        if (document.kimi_detailed_analysis or "").strip():
            context["secondary_kimi_detailed_reading"] = document.kimi_detailed_analysis
            context["secondary_kimi_note"] = "这是辅助解读，不得覆盖或替代 primary_paper_text；若二者冲突，以原文为准。"
        if stage == "PROBLEM_MAP" and overview:
            context["confirmed_overview"] = self._overview_read(overview).model_dump(mode="json")
            context["overview_conversation"] = [
                {"role": item.role.lower(), "content": item.content}
                for item in self.repo.list_messages(study.id, "OVERVIEW")
            ]
        messages: list[dict] = [{"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
        messages.extend({"role": item.role.lower(), "content": item.content} for item in self.repo.list_messages(study.id, stage))
        return messages

    def _add_message(self, study_id: str, stage: str, role: str, content: str) -> PaperStudyMessage:
        message = PaperStudyMessage(
            id=str(uuid4()), study_id=study_id, stage=stage, role=role,
            content=content.strip(), sequence_index=self.repo.next_message_index(study_id, stage),
        )
        return self.repo.add(message)

    def start_conversation(self, study_id: str, stage: str, text_model: str | None = None) -> PaperStudyRead:
        study = self._require_study(study_id)
        self._require_paper_material(study)
        if stage == "PROBLEM_MAP" and self._overview_read(self.repo.get_overview(study.id)).user_status != "CONFIRMED":
            raise AppError("OVERVIEW_CONFIRM_REQUIRED", "请先确认暂定理解，再讨论问题地图", status_code=400)
        if stage not in {"OVERVIEW", "PROBLEM_MAP"}:
            raise AppError("PAPER_STAGE_INVALID", "不支持的论文理解阶段", status_code=400)
        if self.repo.list_messages(study.id, stage):
            return self._study_read(study)
        prompt = OVERVIEW_CONVERSATION_PROMPT if stage == "OVERVIEW" else PROBLEM_MAP_CONVERSATION_PROMPT
        provider, model = self._text_route(text_model)
        content = self._collect(
            provider=provider, model=model, system=prompt,
            messages=self._conversation_context(study, stage),
        )
        self._add_message(study.id, stage, "ASSISTANT", content)
        self.db.commit()
        return self._study_read(study)

    def send_conversation_message(self, study_id: str, payload: PaperStudyMessageCreate) -> PaperStudyRead:
        study = self._require_study(study_id)
        self._require_paper_material(study)
        stage = payload.stage
        if stage == "PROBLEM_MAP" and self._overview_read(self.repo.get_overview(study.id)).user_status != "CONFIRMED":
            raise AppError("OVERVIEW_CONFIRM_REQUIRED", "请先确认暂定理解，再讨论问题地图", status_code=400)
        if not self.repo.list_messages(study.id, stage):
            self.start_conversation(study.id, stage, payload.text_model)
        self._add_message(study.id, stage, "USER", payload.content)
        prompt = OVERVIEW_CONVERSATION_PROMPT if stage == "OVERVIEW" else PROBLEM_MAP_CONVERSATION_PROMPT
        provider, model = self._text_route(payload.text_model)
        content = self._collect(
            provider=provider, model=model, system=prompt,
            messages=self._conversation_context(study, stage),
        )
        self._add_message(study.id, stage, "ASSISTANT", content)
        self.db.commit()
        return self._study_read(study)

    def stream_conversation(
        self,
        study_id: str,
        *,
        stage: str,
        user_content: str | None = None,
        text_model: str | None = None,
    ) -> Iterator[str]:
        """Stream one paper-understanding turn and persist it after completion."""
        full_text = ""
        try:
            study = self._require_study(study_id)
            self._require_paper_material(study)
            if stage not in {"OVERVIEW", "PROBLEM_MAP"}:
                raise AppError("PAPER_STAGE_INVALID", "不支持的论文理解阶段", status_code=400)
            if stage == "PROBLEM_MAP" and self._overview_read(self.repo.get_overview(study.id)).user_status != "CONFIRMED":
                raise AppError("OVERVIEW_CONFIRM_REQUIRED", "请先确认暂定理解，再讨论问题地图", status_code=400)

            existing = self.repo.list_messages(study.id, stage)
            if user_content is None:
                if existing:
                    raise AppError("PAPER_CONVERSATION_ALREADY_STARTED", "这段论文对话已经开始", status_code=400)
            else:
                content = user_content.strip()
                if not content:
                    raise AppError("MESSAGE_EMPTY", "问题不能为空", status_code=400)
                self._add_message(study.id, stage, "USER", content)
                self.db.commit()

            prompt = OVERVIEW_CONVERSATION_PROMPT if stage == "OVERVIEW" else PROBLEM_MAP_CONVERSATION_PROMPT
            provider, model = self._text_route(text_model)
            for chunk in self.gateway.stream(
                provider=provider, model=model,
                system_prompt=prompt, messages=self._conversation_context(study, stage), web_search=False,
            ):
                if chunk.status_text:
                    yield sse_event("status", {"message": chunk.status_text})
                if chunk.content_delta:
                    full_text += chunk.content_delta
                    yield sse_event("delta", {"delta": chunk.content_delta})

            if not full_text.strip():
                raise AppError("LLM_EMPTY_RESPONSE", "模型返回空内容", status_code=502)
            self._add_message(study.id, stage, "ASSISTANT", full_text)
            self.db.commit()
            yield sse_event("completed", {"content": full_text, "stage": stage})
        except AppError as error:
            yield sse_event("failed", {"error_code": error.code, "error_message": error.message})
        except Exception as error:  # noqa: BLE001
            yield sse_event("failed", {"error_code": "PAPER_LLM_UNEXPECTED_ERROR", "error_message": str(error)})

    def update_overview(self, study_id: str, payload: PaperOverviewUpdate) -> PaperStudyRead:
        study = self._require_study(study_id)
        overview = self.repo.get_overview(study.id)
        if overview is None:
            raise NotFoundError("PAPER_OVERVIEW_NOT_FOUND", "论文理解概览不存在")
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(overview, field, value.strip() if isinstance(value, str) else value)
        if overview.user_status == "CONFIRMED":
            required_fields = ("research_context", "core_problem", "main_approach", "claimed_effect", "user_understanding")
            missing = [field for field in required_fields if not str(getattr(overview, field) or "").strip()]
            if missing:
                raise AppError("OVERVIEW_FIELDS_REQUIRED", "请先用自己的话填写研究场景、问题、做法、效果和当前复述，再确认暂定理解", status_code=400)
        self.db.commit()
        return self._study_read(study)
