from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models.context import ContextSnapshot, ContextSnapshotItem
from app.models.message import ChatMessage
from app.repositories.attachment_repo import AttachmentRepository
from app.repositories.context_repo import ContextRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.node_repo import NodeRepository
from app.repositories.session_repo import SessionRepository
from app.repositories.summary_repo import SummaryRepository
from app.schemas.common import ConversationMode, SnapshotSourceType
from app.schemas.context import ContextPreviewRead, SnapshotItemRead
from app.services.context_policy_service import ContextPolicyService
from app.services.history_for_llm import message_text_for_provider
from app.services.llm_prompts import SYSTEM_PROMPT


@dataclass
class ItemDraft:
    source_node_id: str | None
    source_session_id: str | None
    source_type: SnapshotSourceType
    source_entity_id: str
    source_version: int
    rendered_content: str
    order_index: int
    priority: int
    keep_always: bool = False


@dataclass
class BuildResult:
    policy_version: int
    system_prompt: str
    items: list[ItemDraft] = field(default_factory=list)
    truncated: bool = False
    estimated_input_tokens: int = 0
    rendered_context: str = ""
    snapshot_id: str | None = None


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4) if text else 0


class ContextBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.nodes = NodeRepository(db)
        self.sessions = SessionRepository(db)
        self.messages = MessageRepository(db)
        self.summaries = SummaryRepository(db)
        self.contexts = ContextRepository(db)
        self.attachments = AttachmentRepository(db)
        self.policies = ContextPolicyService(db)
        self._attachment_cache: dict[str, list] = {}
        self.target_provider: str = "deepseek"

    def build(
        self,
        session_id: str,
        new_user_message: str = "",
        *,
        persist: bool = False,
        exclude_message_ids: set[str] | None = None,
        target_provider: str = "deepseek",
    ) -> BuildResult:
        self.target_provider = target_provider
        session = self.sessions.get_active(session_id)
        if not session:
            raise NotFoundError("SESSION_NOT_FOUND", f"Session {session_id} not found")
        node = self.nodes.get_active(session.node_id)
        if not node:
            raise NotFoundError("NODE_NOT_FOUND", f"Node {session.node_id} not found")

        self.policies.get_or_create_default(session_id)
        policy = self.contexts.get_policy_by_session(session_id)
        assert policy is not None

        items: list[ItemDraft] = []
        order = 0

        order += 1
        items.append(
            ItemDraft(
                source_node_id=node.id,
                source_session_id=None,
                source_type=SnapshotSourceType.NODE_META,
                source_entity_id=node.id,
                source_version=1,
                rendered_content=f"[当前节点] {node.title}（{node.node_type}）",
                order_index=order,
                priority=20,
            )
        )

        if policy.include_current_node_summary and node.current_summary_version_id:
            summary = self.summaries.get_active(node.current_summary_version_id)
            if summary:
                order += 1
                items.append(
                    ItemDraft(
                        source_node_id=node.id,
                        source_session_id=None,
                        source_type=SnapshotSourceType.CURRENT_NODE_SUMMARY,
                        source_entity_id=summary.id,
                        source_version=summary.version_number,
                        rendered_content=f"[当前节点摘要]\n{summary.content}",
                        order_index=order,
                        priority=30,
                    )
                )

        for node_source in self.contexts.list_active_node_sources(policy.id):
            is_same = node_source.source_node_id == node.id
            if node_source.include_summary and not is_same:
                source_node = self.nodes.get_active(node_source.source_node_id)
                if source_node and source_node.current_summary_version_id:
                    summary = self.summaries.get_active(source_node.current_summary_version_id)
                    if summary:
                        order += 1
                        items.append(
                            ItemDraft(
                                source_node_id=source_node.id,
                                source_session_id=None,
                                source_type=SnapshotSourceType.BORROWED_NODE_SUMMARY,
                                source_entity_id=summary.id,
                                source_version=summary.version_number,
                                rendered_content=f"[借用节点摘要·{source_node.title}]\n{summary.content}",
                                order_index=order,
                                priority=40,
                            )
                        )

            for session_source in node_source.session_sources:
                if session_source.source_session_id == session_id:
                    continue
                borrowed = self._resolve_session_messages(session_source)
                source_type = (
                    SnapshotSourceType.SAME_NODE_SESSION_MESSAGE
                    if is_same
                    else SnapshotSourceType.BORROWED_SESSION_MESSAGE
                )
                label = "本节点其他会话" if is_same else "借用会话"
                for message in borrowed:
                    order += 1
                    body = self._render_message_body(message)
                    items.append(
                        ItemDraft(
                            source_node_id=node_source.source_node_id,
                            source_session_id=session_source.source_session_id,
                            source_type=source_type,
                            source_entity_id=message.id,
                            source_version=message.current_revision,
                            rendered_content=f"[{label}] {message.role}: {body}",
                            order_index=order,
                            priority=60 if is_same else 50,
                        )
                    )

        excluded = exclude_message_ids or set()
        # Current session history is always included for a conversation-scoped policy.
        # Exclude empty streaming placeholders from prior interrupted turns.
        for message in self.messages.list_visible_by_session(session_id):
            if message.id in excluded:
                continue
            if message.status == "STREAMING" and not message.content:
                continue
            order += 1
            body = self._render_message_body(message)
            items.append(
                ItemDraft(
                    source_node_id=node.id,
                    source_session_id=session_id,
                    source_type=SnapshotSourceType.CURRENT_SESSION_MESSAGE,
                    source_entity_id=message.id,
                    source_version=message.current_revision,
                    rendered_content=f"[当前会话] {message.role}: {body}",
                    order_index=order,
                    priority=55,
                )
            )

        new_msg = (new_user_message or "").strip()
        if new_msg:
            order += 1
            items.append(
                ItemDraft(
                    source_node_id=node.id,
                    source_session_id=session_id,
                    source_type=SnapshotSourceType.NEW_USER_MESSAGE,
                    source_entity_id="new-user-message",
                    source_version=1,
                    rendered_content=f"[当前问题]\n{new_msg}",
                    order_index=order,
                    priority=10,
                    keep_always=True,
                )
            )

        system_prompt = SYSTEM_PROMPT
        truncated = False
        max_tokens = policy.max_context_tokens
        if max_tokens is not None and max_tokens > 0:
            items, truncated = self._apply_budget(system_prompt, items, max_tokens)

        rendered_context = "\n\n".join(item.rendered_content for item in items)
        estimated = estimate_tokens(system_prompt) + estimate_tokens(rendered_context)

        result = BuildResult(
            policy_version=policy.policy_version,
            system_prompt=system_prompt,
            items=items,
            truncated=truncated,
            estimated_input_tokens=estimated,
            rendered_context=rendered_context,
        )

        if persist:
            snapshot = ContextSnapshot(
                id=str(uuid4()),
                node_id=node.id,
                session_id=session_id,
                policy_version=policy.policy_version,
                rendered_system_prompt=system_prompt,
                rendered_context=rendered_context,
                estimated_input_tokens=estimated,
                truncated=truncated,
            )
            self.contexts.add_snapshot(snapshot)
            for item in items:
                self.contexts.add_snapshot_item(
                    ContextSnapshotItem(
                        id=str(uuid4()),
                        snapshot_id=snapshot.id,
                        source_node_id=item.source_node_id,
                        source_session_id=item.source_session_id,
                        source_type=item.source_type.value,
                        source_entity_id=item.source_entity_id,
                        source_version=item.source_version,
                        rendered_content=item.rendered_content,
                        order_index=item.order_index,
                    )
                )
            self.db.commit()
            result.snapshot_id = snapshot.id

        return result

    def preview(self, session_id: str, new_user_message: str = "", persist: bool = False) -> ContextPreviewRead:
        result = self.build(session_id, new_user_message, persist=persist)
        return ContextPreviewRead(
            snapshot_id=result.snapshot_id,
            policy_version=result.policy_version,
            rendered_system_prompt=result.system_prompt,
            rendered_context=result.rendered_context,
            estimated_input_tokens=result.estimated_input_tokens,
            truncated=result.truncated,
            items=[
                SnapshotItemRead(
                    source_node_id=i.source_node_id,
                    source_session_id=i.source_session_id,
                    source_type=i.source_type,
                    source_entity_id=i.source_entity_id,
                    source_version=i.source_version,
                    rendered_content=i.rendered_content,
                    order_index=i.order_index,
                )
                for i in result.items
            ],
        )

    def _resolve_session_messages(self, session_source) -> list[ChatMessage]:
        mode = ConversationMode(session_source.conversation_mode)
        messages = self.messages.list_visible_by_session(session_source.source_session_id)
        if mode == ConversationMode.FULL_SESSION:
            return messages
        if mode == ConversationMode.LAST_N_TURNS:
            n = session_source.last_n_turns or 1
            return messages[-(n * 2) :]
        if mode == ConversationMode.SELECTED_MESSAGES:
            selected = set(json.loads(session_source.selected_message_ids or "[]"))
            return [m for m in messages if m.id in selected]
        return []

    def _attachments_for_message(self, message_id: str):
        if message_id not in self._attachment_cache:
            self._attachment_cache[message_id] = self.attachments.list_by_message_ids([message_id])
        return self._attachment_cache[message_id]

    def _render_message_body(self, message: ChatMessage) -> str:
        # Cross-vendor: only final text (+ same-vendor notes). Raw images are never re-sent here.
        parts = [message_text_for_provider(message, target_provider=self.target_provider)]
        for attachment in self._attachments_for_message(message.id):
            kind = getattr(attachment, "kind", None) or "pdf"
            if kind == "image":
                parts.append(f"[图片附件 {attachment.filename}]（像素内容见当时助手解析正文）")
            elif attachment.extracted_text:
                parts.append(f"[附件 {attachment.filename}]\n{attachment.extracted_text}")
            else:
                parts.append(f"[附件 {attachment.filename}]（未能提取文本）")
        return "\n\n".join(p for p in parts if p)

    def _apply_budget(
        self,
        system_prompt: str,
        items: list[ItemDraft],
        max_tokens: int,
    ) -> tuple[list[ItemDraft], bool]:
        def total(candidate: list[ItemDraft]) -> int:
            body = "\n\n".join(i.rendered_content for i in candidate)
            return estimate_tokens(system_prompt) + estimate_tokens(body)

        if total(items) <= max_tokens:
            return items, False

        drop_order = sorted(
            [i for i in items if not i.keep_always],
            key=lambda i: (-i.priority, i.order_index),
        )
        remaining = list(items)
        truncated = False
        for victim in drop_order:
            if total(remaining) <= max_tokens:
                break
            remaining = [i for i in remaining if i is not victim]
            truncated = True

        remaining.sort(key=lambda i: i.order_index)
        return remaining, truncated
