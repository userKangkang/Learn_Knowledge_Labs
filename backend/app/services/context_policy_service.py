from uuid import uuid4

from sqlalchemy.orm import Session

from app.errors import AppError, NotFoundError
from app.models.context import ContextNodeSource, ContextSessionSource, SessionContextPolicy
from app.models.node import KnowledgeNode
from app.models.session import ConversationSession
from app.repositories.context_repo import ContextRepository
from app.repositories.node_repo import NodeRepository
from app.repositories.session_repo import SessionRepository
from app.schemas.common import ConversationMode
from app.schemas.context import (
    CandidateNodeRead,
    ContextCandidatesRead,
    ContextPolicyRead,
    ContextPolicyUpdate,
    NodeSourceCreate,
    NodeSourceRead,
    SessionSourceRead,
)
from app.services.ancestry import ancestor_generations, classify_source_node


class ContextPolicyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.nodes = NodeRepository(db)
        self.sessions = SessionRepository(db)
        self.contexts = ContextRepository(db)

    def _require_session(self, session_id: str) -> ConversationSession:
        session = self.sessions.get_active(session_id)
        if not session:
            raise NotFoundError("SESSION_NOT_FOUND", f"Session {session_id} not found")
        return session

    def _require_node(self, node_id: str) -> KnowledgeNode:
        node = self.nodes.get_active(node_id)
        if not node:
            raise NotFoundError("NODE_NOT_FOUND", f"Node {node_id} not found")
        return node

    def get_or_create_default(self, session_id: str) -> SessionContextPolicy:
        session = self._require_session(session_id)
        policy = self.contexts.get_policy_by_session(session.id)
        if policy:
            return policy
        policy = SessionContextPolicy(
            id=str(uuid4()),
            session_id=session.id,
            include_current_node_summary=False,
            max_context_tokens=None,
            policy_version=1,
        )
        self.contexts.add_policy(policy)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def _validate_session_source(
        self,
        source_node_id: str,
        payload_session,
        *,
        current_session_id: str,
    ) -> None:
        mode = payload_session.conversation_mode
        if mode == ConversationMode.NONE:
            raise AppError("INVALID_CONVERSATION_MODE", "NONE is not allowed for session sources", status_code=400)
        if mode == ConversationMode.LAST_N_TURNS and (not payload_session.last_n_turns or payload_session.last_n_turns < 1):
            raise AppError("LAST_N_REQUIRED", "last_n_turns is required for LAST_N_TURNS", status_code=400)
        if mode == ConversationMode.SELECTED_MESSAGES and not payload_session.selected_message_ids:
            raise AppError("SELECTED_MESSAGES_REQUIRED", "selected_message_ids required", status_code=400)

        if payload_session.source_session_id == current_session_id:
            raise AppError(
                "CANNOT_BORROW_CURRENT_SESSION",
                "Cannot borrow the current session; its history is always included",
                status_code=400,
            )

        session = self.sessions.get_active(payload_session.source_session_id)
        if not session or session.node_id != source_node_id:
            raise AppError("SESSION_NODE_MISMATCH", "Session does not belong to source node", status_code=400)

    def _validate_sources(
        self,
        node: KnowledgeNode,
        sources: list[NodeSourceCreate],
        *,
        current_session_id: str,
    ) -> None:
        ancestor_ids = set(ancestor_generations(self.db, node.id, node.graph_id, max_gen=3).keys())
        non_ancestor_count = 0
        seen_nodes: set[str] = set()

        for source in sources:
            if source.source_node_id in seen_nodes:
                raise AppError("DUPLICATE_SOURCE_NODE", "Each source node may appear only once", status_code=400)
            seen_nodes.add(source.source_node_id)

            try:
                kind = classify_source_node(self.db, node.id, source.source_node_id, node.graph_id)
            except ValueError:
                raise NotFoundError("SOURCE_NODE_NOT_FOUND", f"Source node {source.source_node_id} not found") from None

            if kind == "SAME_NODE":
                if source.include_summary:
                    raise AppError(
                        "SAME_NODE_SUMMARY_FORBIDDEN",
                        "Same-node sources cannot include summary; use the global summary switch",
                        status_code=400,
                    )
                if not source.sessions:
                    raise AppError("SAME_NODE_SESSION_REQUIRED", "Same-node source needs at least one session", status_code=400)
            elif kind == "ANCESTOR":
                if source.source_node_id not in ancestor_ids:
                    raise AppError("NOT_ANCESTOR", "Source is not within 3 ancestor generations", status_code=400)
            else:
                non_ancestor_count += 1
                if non_ancestor_count > 2:
                    raise AppError(
                        "NON_ANCESTOR_LIMIT",
                        "At most 2 non-ancestor nodes can be borrowed",
                        status_code=400,
                    )

            if not source.include_summary and not source.sessions:
                raise AppError("EMPTY_SOURCE", "Source must include summary and/or sessions", status_code=400)

            for session_src in source.sessions:
                self._validate_session_source(
                    source.source_node_id,
                    session_src,
                    current_session_id=current_session_id,
                )

    def _to_read(self, policy: SessionContextPolicy, node: KnowledgeNode) -> ContextPolicyRead:
        ancestors = ancestor_generations(self.db, node.id, node.graph_id, max_gen=3)
        sources_out: list[NodeSourceRead] = []
        for source in self.contexts.list_active_node_sources(policy.id):
            kind = "SAME_NODE" if source.source_node_id == node.id else (
                "ANCESTOR" if source.source_node_id in ancestors else "NON_ANCESTOR"
            )
            sessions = [
                SessionSourceRead(
                    id=s.id,
                    source_session_id=s.source_session_id,
                    conversation_mode=ConversationMode(s.conversation_mode),
                    last_n_turns=s.last_n_turns,
                    selected_message_ids=list(s.selected_message_ids or []),
                    order_index=s.order_index,
                )
                for s in source.session_sources
            ]
            sources_out.append(
                NodeSourceRead(
                    id=source.id,
                    source_node_id=source.source_node_id,
                    include_summary=source.include_summary,
                    order_index=source.order_index,
                    is_same_node=kind == "SAME_NODE",
                    is_ancestor=kind == "ANCESTOR",
                    sessions=sessions,
                )
            )
        return ContextPolicyRead(
            id=policy.id,
            session_id=policy.session_id,
            node_id=node.id,
            include_current_node_summary=policy.include_current_node_summary,
            include_current_session_history=True,
            max_context_tokens=policy.max_context_tokens,
            policy_version=policy.policy_version,
            sources=sources_out,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )

    def get_policy(self, session_id: str) -> ContextPolicyRead:
        session = self._require_session(session_id)
        node = self._require_node(session.node_id)
        self.get_or_create_default(session_id)
        policy = self.contexts.get_policy_by_session(session_id)
        if policy is None:
            raise AppError("CONTEXT_POLICY_MISSING", "上下文策略初始化失败", status_code=500)
        return self._to_read(policy, node)

    def replace_policy(self, session_id: str, payload: ContextPolicyUpdate) -> ContextPolicyRead:
        session = self._require_session(session_id)
        node = self._require_node(session.node_id)
        self._validate_sources(node, payload.sources, current_session_id=session_id)
        policy = self.get_or_create_default(session_id)

        policy.include_current_node_summary = payload.include_current_node_summary
        policy.max_context_tokens = payload.max_context_tokens
        policy.policy_version += 1

        self.contexts.soft_delete_sources_for_policy(policy.id)

        for source_payload in sorted(payload.sources, key=lambda s: s.order_index):
            node_source = ContextNodeSource(
                id=str(uuid4()),
                context_policy_id=policy.id,
                source_node_id=source_payload.source_node_id,
                include_summary=source_payload.include_summary and source_payload.source_node_id != node.id,
                order_index=source_payload.order_index,
            )
            self.contexts.add_node_source(node_source)
            for idx, session_payload in enumerate(sorted(source_payload.sessions, key=lambda s: s.order_index)):
                self.contexts.add_session_source(
                    ContextSessionSource(
                        id=str(uuid4()),
                        context_node_source_id=node_source.id,
                        source_session_id=session_payload.source_session_id,
                        conversation_mode=session_payload.conversation_mode.value,
                        last_n_turns=session_payload.last_n_turns,
                        selected_message_ids=list(session_payload.selected_message_ids or []),
                        order_index=session_payload.order_index if session_payload.order_index else idx,
                    )
                )

        self.db.commit()
        policy = self.contexts.get_policy_by_session(session_id)
        if policy is None:
            raise AppError("CONTEXT_POLICY_MISSING", "上下文策略保存后无法读取", status_code=500)
        return self._to_read(policy, node)

    def list_candidates(self, session_id: str) -> ContextCandidatesRead:
        session = self._require_session(session_id)
        node = self._require_node(session.node_id)
        ancestors = ancestor_generations(self.db, node.id, node.graph_id, max_gen=3)
        all_nodes = self.nodes.list_active_by_graph(node.graph_id)

        ancestor_list: list[CandidateNodeRead] = []
        non_ancestor_list: list[CandidateNodeRead] = []
        for n in all_nodes:
            if n.id == node.id:
                continue
            if n.id in ancestors:
                ancestor_list.append(
                    CandidateNodeRead(id=n.id, title=n.title, node_type=n.node_type, generation=ancestors[n.id])
                )
            else:
                non_ancestor_list.append(
                    CandidateNodeRead(id=n.id, title=n.title, node_type=n.node_type, generation=None)
                )

        ancestor_list.sort(key=lambda x: (x.generation or 99, x.title))
        non_ancestor_list.sort(key=lambda x: x.title)
        return ContextCandidatesRead(ancestors=ancestor_list, non_ancestors=non_ancestor_list)
