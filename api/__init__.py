"""
Sira API package.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from .dependencies import lifespan
from .routes import register_routes


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Sira API",
        lifespan=lifespan
    )
    
    # Serve uploads
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
    app.mount("/api/uploads", StaticFiles(directory="uploads"), name="uploads")
    
    register_routes(app)
    
    return app


# Default app instance
app = create_app()
