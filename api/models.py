"""
Pydantic models for the Instagram Assistant API.
"""
from typing import List, Optional
from pydantic import BaseModel


class Message(BaseModel):
    """A single message in a conversation."""
    role: str
    content: str
    timestamp: str
    sources: Optional[List[dict]] = None


class Conversation(BaseModel):
    """A conversation with messages."""
    id: str
    title: str
    created_at: str
    updated_at: str
    is_favorite: bool = False
    messages: List[Message] = []


class ChatRequest(BaseModel):
    """Request body for chat endpoints."""
    message: str
    conversation_id: Optional[str] = None
    model: Optional[str] = None
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
    message_count: int


class ConversationUpdate(BaseModel):
    """Request body for updating conversations."""
    title: Optional[str] = None
    is_favorite: Optional[bool] = None


class TitleEvaluationRequest(BaseModel):
    """Request body for title evaluation."""
    message: str
    model: Optional[str] = None
