"""
Handler for discovery queries (lists, exploration).
"""
import json
import uuid
from datetime import datetime
from typing import AsyncGenerator

from api.models import ChatRequest
from api.storage import get_conversation, save_conversation
from api.dependencies import get_analytics


async def handle_discovery_query(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Handle discovery queries (lists, exploration)."""
    analytics = get_analytics()
    
    conv_id = request.conversation_id
    if conv_id:
        conv = get_conversation(conv_id)
        if not conv:
            yield f"data: {json.dumps({'error': 'Conversation not found'})}\n\n"
            return
    else:
        conv_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        conv = {
            "id": conv_id,
            "title": request.message[:50] + ("..." if len(request.message) > 50 else ""),
            "created_at": now,
            "updated_at": now,
            "messages": []
        }

    yield f"data: {json.dumps({'type': 'conversation_id', 'id': conv_id})}

"

    # Add user message
    user_msg = {
        "role": "user",
        "content": request.message,
        "timestamp": datetime.now().isoformat()
    }
    conv['messages'].append(user_msg)

    try:
        yield f"data: {json.dumps({'type': 'progress', 'step': 'analytics', 'message': 'Exploring data...'})}\n\n"

        # Default: list all participants
        stats = analytics.get_participant_stats()

        # Format response
        if stats:
            response_text = "**Participants and Statistics:**\n\n"
            for participant, info in list(stats.items())[:20]:  # Top 20
                response_text += f"• **{participant}**: {info['message_count']} messages, {info['conversations']} conversations\n"
        else:
            response_text = "No participants found in conversations."

        yield f"data: {json.dumps({'type': 'chunk', 'content': response_text})}

"

    except Exception as e:
        response_text = f"Exploration error: {str(e)}"
        yield f"data: {json.dumps({'type': 'chunk', 'content': response_text})}

"

    # Save conversation
    assistant_msg = {
        "role": "assistant",
        "content": response_text,
        "timestamp": datetime.now().isoformat(),
        "sources": [],
        "summary_sources": []
    }
    conv['messages'].append(assistant_msg)
    conv['updated_at'] = datetime.now().isoformat()
    save_conversation(conv)

    yield f"data: {json.dumps({'type': 'done'})}\n\n"