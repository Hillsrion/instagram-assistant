"""
Status and system routes.
"""
import httpx
from fastapi import APIRouter, HTTPException

from api.dependencies import get_config, get_retriever

router = APIRouter()


@router.get("/status")
async def get_status():
    """Get system status."""
    config = get_config()
    retriever = get_retriever()
    
    return {
        "status": "ready" if retriever else "initializing",
        "model": config.llm_model if config else None,
        "chunks_loaded": len(retriever.vector_store.chunks) if retriever else 0
    }


@router.get("/ollama/models")
async def list_ollama_models():
    """List available Ollama models and return the default model."""
    config = get_config()
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.ollama_url}/api/tags",
                timeout=5.0
            )
            response.raise_for_status()
            data = response.json()

        models = []
        for model in data.get("models", []):
            models.append({
                "name": model["name"],
                "size": model.get("size", 0),
                "modified_at": model.get("modified_at", "")
            })

        return {
            "models": models,
            "default_model": config.llm_model
        }

    except Exception as e:
        print(f"Error listing Ollama models: {e}")
        raise HTTPException(status_code=503, detail="Cannot reach Ollama")
