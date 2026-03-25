"""
Pydantic models for the Sira API.
"""
from typing import List, Optional
from pydantic import BaseModel


class FileAttachment(BaseModel):
    """A file attached to a message."""
    id: str
    name: str
    type: str  # image, document, etc.
    url: str
    size: Optional[int] = None


class Message(BaseModel):
    """A single message in a conversation."""
    role: str
    content: str
    timestamp: str
    sources: Optional[List[dict]] = None
    followups: Optional[List[str]] = None
    attachments: Optional[List[FileAttachment]] = None


class Project(BaseModel):
    """A project to group conversations."""
    id: str
    title: str
    description: Optional[str] = None
    tone: Optional[str] = None
    instructions: Optional[str] = None
    created_at: str
    updated_at: str


class Conversation(BaseModel):
    """A conversation with messages."""
    id: str
    title: str
    created_at: str
    updated_at: str
    is_favorite: bool = False
    project_id: Optional[str] = None
    messages: List[Message] = []


class ChatRequest(BaseModel):
    """Request body for chat endpoints."""
    message: str
    attachments: Optional[List[FileAttachment]] = None
    conversation_id: Optional[str] = None
    project_id: Optional[str] = None
    model: Optional[str] = None
    mode: Optional[str] = "fast" # NEW: mode selector (fast, reflexion)
    agent_id: Optional[str] = None # Persona selector (standard, nostalgique, analyste)
    participant_filter: Optional[str] = None
    about_person: Optional[str] = None 
    use_about_person: bool = False # NEW: toggle between strict and broad person search
    group_filter: Optional[str] = None 
    year_filter: Optional[int] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    use_reranking: bool = True
    use_hybrid: bool = True
    expand_context: bool = True


class ConversationListResponse(BaseModel):
    """Simplified conversation info for listing."""
    id: str
    title: str
    created_at: str
    updated_at: str
    is_favorite: bool = False
    project_id: Optional[str] = None
    message_count: int


class ProjectListResponse(BaseModel):
    """Simplified project info for listing."""
    id: str
    title: str
    description: Optional[str] = None
    created_at: str
    updated_at: str


class ProjectUpdate(BaseModel):
    """Request body for updating projects."""
    title: Optional[str] = None
    description: Optional[str] = None
    tone: Optional[str] = None
    instructions: Optional[str] = None


class ConversationUpdate(BaseModel):
    """Request body for updating conversations."""
    title: Optional[str] = None
    is_favorite: Optional[bool] = None
    project_id: Optional[str] = None


class TitleEvaluationRequest(BaseModel):
    """Request body for title evaluation."""
    message: str
    model: Optional[str] = None


class ProjectBulkUpdate(BaseModel):
    """Request body for bulk updating conversations in a project."""
    conversation_ids: List[str]
    action: str  # "add", "remove", or "set"


class InstagramThread(BaseModel):
    """Represents a source Instagram conversation (thread)."""
    id: str  # The conversation_id from metadata.db
    participants: List[str]
    summary: str
    message_count: int
    date_range: str


class SourceGroup(BaseModel):
    """A user-defined group of source Instagram threads."""
    id: str
    title: str
    thread_ids: List[str]
    created_at: str
    updated_at: str


class SourceGroupUpdate(BaseModel):
    """Request body for creating/updating source groups."""
    title: str


class SourceGroupBulkUpdate(BaseModel):
    """Request body for bulk updating threads in a source group."""
    thread_ids: List[str]
    action: str  # "add", "remove"
