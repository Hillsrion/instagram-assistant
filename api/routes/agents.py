"""
Agent personas API routes.
"""
from fastapi import APIRouter
from rag_pipeline.chat.personas import get_all_personas

router = APIRouter()


@router.get("/agents")
async def list_agents():
    """Returns all available agent personas."""
    return [
        {
            "id": p.id,
            "name": p.name,
            "icon": p.icon,
            "description": p.description,
        }
        for p in get_all_personas()
    ]
