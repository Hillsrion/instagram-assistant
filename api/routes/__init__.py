"""
API Routes package.
"""
from fastapi import APIRouter

from .status import router as status_router
from .conversations import router as conversations_router
from .participants import router as participants_router
from .analytics import router as analytics_router
from .chat import router as chat_router
from .projects import router as projects_router
from .settings import router as settings_router
from .files import router as files_router
from .agents import router as agents_router


def register_routes(app):
    """Register all route modules to the FastAPI app."""
    app.include_router(status_router, prefix="/api", tags=["status"])
    app.include_router(conversations_router, prefix="/api", tags=["conversations"])
    app.include_router(participants_router, prefix="/api", tags=["participants"])
    app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])
    app.include_router(chat_router, prefix="/api", tags=["chat"])
    app.include_router(projects_router, prefix="/api", tags=["projects"])
    app.include_router(settings_router, prefix="/api", tags=["settings"])
    app.include_router(files_router, prefix="/api", tags=["files"])
    app.include_router(agents_router, prefix="/api", tags=["agents"])
