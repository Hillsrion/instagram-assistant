"""
Project registration and management routes.
"""
import uuid
from typing import List
from datetime import datetime

from fastapi import APIRouter, HTTPException

from api.models import (
    Project,
    ProjectUpdate,
    ProjectListResponse,
    ConversationListResponse
)
from api.storage import (
    load_projects,
    get_project,
    save_project,
    delete_project,
    load_conversations
)

router = APIRouter()


@router.get("/projects", response_model=List[ProjectListResponse])
async def list_projects():
    """List all projects."""
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


@router.post("/projects", response_model=Project)
async def create_project(data: ProjectUpdate):
    """Create a new project."""
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


@router.get("/projects/{project_id}", response_model=Project)
async def get_project_detail(project_id: str):
    """Get a project with all details."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/projects/{project_id}")
async def delete_project_endpoint(project_id: str):
    """Delete a project."""
    if delete_project(project_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Project not found")


@router.patch("/projects/{project_id}", response_model=Project)
async def update_project_endpoint(project_id: str, data: ProjectUpdate):
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


@router.get("/projects/{project_id}/conversations", response_model=List[ConversationListResponse])
async def list_project_conversations(project_id: str):
    """List all conversations belonging to a project."""
    conversations = load_conversations()
    project_convs = [
        c for c in conversations.values()
        if c.get('project_id') == project_id
    ]
    
    sorted_convs = sorted(
        project_convs,
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
        for c in sorted_convs
    ]
