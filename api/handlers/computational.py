"""
Handler for computational queries (counting, stats).
"""
import json
import uuid
from datetime import datetime
from typing import AsyncGenerator

from api.models import ChatRequest
from api.storage import get_conversation, save_conversation
from api.dependencies import get_analytics


async def handle_computational_query(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Handle computational queries (counting, stats)."""
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

    yield f"data: {json.dumps({'type': 'conversation_id', 'id': conv_id})}\n\n"

    # Add user message
    user_msg = {
        "role": "user",
        "content": request.message,
        "timestamp": datetime.now().isoformat()
    }
    conv['messages'].append(user_msg)

    # Determine which analytics endpoint to call
    query_lower = request.message.lower()

    try:
        if "combien" in query_lower or "nombre" in query_lower or "count" in query_lower:
            yield f"data: {json.dumps({'type': 'progress', 'step': 'analytics', 'message': 'Calcul des statistiques...'})}\n\n"

            # Extract participant if mentioned
            participant = request.participant_filter
            count = analytics.count_messages(
                participant=participant,
                date_start=request.date_start,
                date_end=request.date_end
            )
            response_text = f"Il y a **{count}** messages"
            if participant:
                response_text += f" avec {participant}"
            if request.date_start or request.date_end:
                response_text += f" entre {request.date_start or 'le début'} et {request.date_end or 'maintenant'}"
            response_text += "."
        else:
            # This branch should rarely be hit since QueryAnalyzer should catch unsupported analytics queries
            yield f"data: {json.dumps({'type': 'progress', 'step': 'analytics', 'message': 'Récupération des données...'})}\n\n"
            response_text = "Je peux compter le nombre de messages totaux ou par contact. Pour d'autres analyses, essayez de reformuler votre question en utilisant 'combien' ou 'nombre'. Sinon, je peux chercher du contenu spécifique dans vos conversations."

        yield f"data: {json.dumps({'type': 'chunk', 'content': response_text})}\n\n"

    except Exception as e:
        response_text = f"Erreur lors du calcul: {str(e)}"
        yield f"data: {json.dumps({'type': 'chunk', 'content': response_text})}\n\n"

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
