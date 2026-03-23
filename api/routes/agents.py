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
            "allowed_tools": list(p.allowed_tools) if p.allowed_tools else None,
        }
        for p in get_all_personas()
    ]
