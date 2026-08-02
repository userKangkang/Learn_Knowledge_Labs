from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import db_session
from app.db.base import Base
from app.main import app
from app.models import (  # noqa: F401
    ChatMessage,
    ContextNodeSource,
    ContextSessionSource,
    ContextSnapshot,
    ContextSnapshotItem,
    ConversationBranch,
    ConversationSession,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    LLMRequest,
    MessageAttachment,
    MessageRevision,
    NodeSummaryVersion,
    SessionContextPolicy,
)


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_db_session() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[db_session] = override_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
