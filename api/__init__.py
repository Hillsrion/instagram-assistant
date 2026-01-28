"""
Instagram Assistant API package.
"""
from fastapi import FastAPI

from .dependencies import lifespan
from .routes import register_routes


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Instagram Conversations Assistant",
        lifespan=lifespan
    )
    
    register_routes(app)
    
    return app


# Default app instance
app = create_app()
