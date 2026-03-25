"""
API Routes package.
"""
from fastapi import APIRouter
from .status import router as status_router
from .participants import router as participants_router
from .analytics import router as analytics_router
from .chat import router as chat_router
from .settings import router as settings_router
from .files import router as files_router
from .agents import router as agents_router
from .chats import router as chats_router
from .chat_projects import router as chat_projects_router
from .instagram_groups import router as instagram_groups_router

def register_routes(app):
    """Register all route modules to the FastAPI app."""
    app.include_router(status_router, prefix="/api", tags=["status"])
    app.include_router(chats_router, prefix="/api", tags=["chats"])
    app.include_router(participants_router, prefix="/api", tags=["participants"])
    app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])
    app.include_router(chat_router, prefix="/api", tags=["chat"])
    app.include_router(settings_router, prefix="/api", tags=["settings"])
    app.include_router(files_router, prefix="/api", tags=["files"])
    app.include_router(agents_router, prefix="/api", tags=["agents"])
    app.include_router(chat_projects_router, prefix="/api", tags=["chat_projects"])
    app.include_router(instagram_groups_router, prefix="/api", tags=["instagram"])
