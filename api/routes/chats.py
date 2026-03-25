"""
Conversation CRUD routes.
"""
import uuid
from typing import List
from datetime import datetime

from fastapi import APIRouter, HTTPException

from api.models import (
    ChatUpdate,
    ChatListResponse,
    TitleEvaluationRequest
)
from api.storage import (
    load_chats,
    get_chat,
    save_chat,
    delete_chat,
    save_chats
)
from api.dependencies import get_chatbot

router = APIRouter()


@router.get("/chats", response_model=List[ChatListResponse])
async def list_chats():
    """List all chats."""
    chats = load_chats()
    # Sort by updated_at descending
    sorted_chats = sorted(
        chats.values(),
        key=lambda x: x.get('updated_at', ''),
        reverse=True
    )
    # Return without full message history for performance
    return [
        {
            "id": c['id'],
            "title": c['title'],
            "created_at": c['created_at'],
            "updated_at": c['updated_at'],
            "is_favorite": c.get('is_favorite', False),
            "message_count": len(c.get('messages', []))
        }
        for c in sorted_chats
    ]


@router.post("/chats")
async def create_chat(data: ChatUpdate):
    """Create a new chat."""
    chat_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    chat_data = {
        "id": chat_id,
        "title": data.title or "New Chat",
        "created_at": now,
        "updated_at": now,
        "is_favorite": data.is_favorite if data.is_favorite is not None else False,
        "messages": []
    }

    save_chat(chat_data)
    return chat_data


@router.delete("/chats")
async def delete_all_chats_endpoint():
    """Delete all chats."""
    save_chats({})
    return {"status": "all chats deleted"}


@router.get("/chats/export")
async def export_chats_endpoint():
    """Export all chats as a JSON."""
    return load_chats()


@router.get("/chats/{chat_id}")
async def get_chat_detail(chat_id: str):
    """Get a chat with all messages."""
    chat_data = get_chat(chat_id)
    if not chat_data:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat_data


@router.delete("/chats/{chat_id}")
async def delete_chat_endpoint(chat_id: str):
    """Delete a chat."""
    if delete_chat(chat_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Chat not found")


@router.patch("/chats/{chat_id}")
async def update_chat_endpoint(chat_id: str, data: ChatUpdate):
    """Update chat properties."""
    chat_data = get_chat(chat_id)
    if not chat_data:
        raise HTTPException(status_code=404, detail="Chat not found")

    if data.title is not None:
        chat_data['title'] = data.title
        
    if data.is_favorite is not None:
        chat_data['is_favorite'] = data.is_favorite
        
    if data.project_id is not None:
        chat_data['project_id'] = data.project_id

    chat_data['updated_at'] = datetime.now().isoformat()
    save_chat(chat_data)

    return chat_data


@router.post("/evaluate-title")
async def evaluate_conversation_title(data: TitleEvaluationRequest):
    """
    Evaluate and generate a title for a conversation based on the first message.
    """
    chatbot = get_chatbot()
    if not chatbot:
        raise HTTPException(status_code=503, detail="Chatbot not initialized")
    
    from anyio.to_thread import run_sync
    try:
        title = await run_sync(chatbot.evaluate_title, data.message, data.model)
        return {"title": title}
    except Exception as e:
        print(f"Error in evaluate-title endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))