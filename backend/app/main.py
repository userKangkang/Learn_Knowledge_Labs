from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import attachments, contexts, edges, graphs, health, llm, messages, nodes, sessions, summaries
from app.config import get_settings
from app.errors import register_exception_handlers

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.4.0")
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = settings.api_v1_prefix
app.include_router(health.router, prefix=api)
app.include_router(graphs.router, prefix=api)
app.include_router(nodes.router, prefix=api)
app.include_router(edges.router, prefix=api)
app.include_router(summaries.router, prefix=api)
app.include_router(sessions.router, prefix=api)
app.include_router(messages.router, prefix=api)
app.include_router(contexts.router, prefix=api)
app.include_router(attachments.router, prefix=api)
app.include_router(llm.router, prefix=api)
