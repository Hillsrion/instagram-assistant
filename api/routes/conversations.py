"""
Conversation CRUD routes.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from api.models import ConversationCreate, TitleEvaluationRequest
from api.storage import (
    load_conversations, 
    get_conversation, 
    save_conversation,
    delete_conversation
)
from api.dependencies import get_chatbot

router = APIRouter()


@router.get("/conversations")
async def list_conversations():
    """List all conversations."""
    conversations = load_conversations()
    # Sort by updated_at descending
    sorted_convs = sorted(
        conversations.values(),
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
            "message_count": len(c.get('messages', []))
        }
        for c in sorted_convs
    ]


@router.post("/conversations")
async def create_conversation(data: ConversationCreate):
    """Create a new conversation."""
    conv_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    conv = {
        "id": conv_id,
        "title": data.title or "New Conversation",
        "created_at": now,
        "updated_at": now,
        "messages": []
    }

    save_conversation(conv)
    return conv


@router.get("/conversations/{conv_id}")
async def get_conversation_detail(conv_id: str):
    """Get a conversation with all messages."""
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/conversations/{conv_id}")
async def delete_conversation_endpoint(conv_id: str):
    """Delete a conversation."""
    if delete_conversation(conv_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Conversation not found")


@router.patch("/conversations/{conv_id}")
async def update_conversation(conv_id: str, data: ConversationCreate):
    """Update conversation title."""
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if data.title:
        conv['title'] = data.title
        conv['updated_at'] = datetime.now().isoformat()
        save_conversation(conv)

    return conv


@router.post("/evaluate-title")
async def evaluate_conversation_title(data: TitleEvaluationRequest):
    """
    Evaluate and generate a title for a conversation based on the first message.
    """
    chatbot = get_chatbot()
    if not chatbot:
        raise HTTPException(status_code=503, detail="Chatbot not initialized")
    
    try:
        title = chatbot.evaluate_title(data.message, model=data.model)
        return {"title": title}
    except Exception as e:
        print(f"Error in evaluate-title endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))