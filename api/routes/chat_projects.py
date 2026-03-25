"""
Project registration and management routes.
"""
import uuid
from typing import List
from datetime import datetime

from fastapi import APIRouter, HTTPException
from api.models import (
    ChatProject,
    ChatProjectUpdate,
    ChatProjectListResponse,
    ChatListResponse,
    ChatProjectBulkUpdate
)
from api.storage import (
    load_projects,
    get_project,
    save_project,
    delete_project,
    load_chats,
    save_chats
)

router = APIRouter()


@router.get("/projects", response_model=List[ChatProjectListResponse])
async def list_projects():
    """List all chat projects."""
    projects = load_projects()
    sorted_projects = sorted(
        projects.values(),
        key=lambda x: x.get('updated_at', ''),
        reverse=True
    )
    return [
        {
            "id": p['id'],
            "title": p['title'],
            "description": p.get('description'),
            "created_at": p['created_at'],
            "updated_at": p['updated_at']
        }
        for p in sorted_projects
    ]


@router.post("/projects", response_model=ChatProject)
async def create_project(data: ChatProjectUpdate):
    """Create a new chat project."""
    project_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    project = {
        "id": project_id,
        "title": data.title or "New Project",
        "description": data.description,
        "tone": data.tone,
        "instructions": data.instructions,
        "created_at": now,
        "updated_at": now
    }

    save_project(project)
    return project


@router.get("/projects/{project_id}", response_model=ChatProject)
async def get_project_detail(project_id: str):
    """Get a chat project with all details."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/projects/{project_id}")
async def delete_project_endpoint(project_id: str):
    """Delete a chat project."""
    if delete_project(project_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Project not found")


@router.patch("/projects/{project_id}", response_model=ChatProject)
async def update_project_endpoint(project_id: str, data: ChatProjectUpdate):
    """Update project details."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if data.title is not None:
        project['title'] = data.title
    if data.description is not None:
        project['description'] = data.description
    if data.tone is not None:
        project['tone'] = data.tone
    if data.instructions is not None:
        project['instructions'] = data.instructions

    project['updated_at'] = datetime.now().isoformat()
    save_project(project)

    return project


@router.get("/projects/{project_id}/chats", response_model=List[ChatListResponse])
async def list_project_chats(project_id: str):
    """List all chats belonging to a project."""
    chats = load_chats()
    project_chats = [
        c for c in chats.values()
        if c.get('project_id') == project_id
    ]
    
    sorted_chats = sorted(
        project_chats,
        key=lambda x: x.get('updated_at', ''),
        reverse=True
    )

    return [
        {
            "id": c['id'],
            "title": c['title'],
            "created_at": c['created_at'],
            "updated_at": c['updated_at'],
            "is_favorite": c.get('is_favorite', False),
            "project_id": c.get('project_id'),
            "message_count": len(c.get('messages', []))
        }
        for c in sorted_chats
    ]


@router.post("/projects/{project_id}/chats/bulk")
async def bulk_update_project_chats(project_id: str, data: ChatProjectBulkUpdate):
    """Bulk add or remove chats from a project."""
    projects = load_projects()
    if project_id != "none" and project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")

    chats = load_chats()
    updated_count = 0
    
    target_project_id = None if project_id == "none" else project_id

    for chat_id in data.chat_ids:
        if chat_id in chats:
            if data.action == "add":
                chats[chat_id]["project_id"] = target_project_id
                updated_count += 1
            elif data.action == "remove":
                if chats[chat_id].get("project_id") == target_project_id:
                    chats[chat_id]["project_id"] = None
                    updated_count += 1
            elif data.action == "set":
                chats[chat_id]["project_id"] = target_project_id
                updated_count += 1

    if updated_count > 0:
        save_chats(chats)

    return {"status": "success", "updated_count": updated_count}
