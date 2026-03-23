"""
Chat routes - main chat and streaming endpoints.
Binary routing: fast-path (direct retrieval) vs agent.
"""
import json
import uuid
import asyncio
from datetime import datetime
from typing import AsyncGenerator
from anyio.to_thread import run_sync

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.models import ChatRequest
from api.storage import get_conversation, save_conversation
from api.utils import get_image_base64
from api.dependencies import (
    get_retriever,
    get_chatbot,
    get_query_analyzer,
    get_agent_runner,
    get_config
)
from api.routing import should_use_agent
from rag_pipeline.chat.personas import get_persona
from rag_pipeline.core.logger import get_logger

logger = get_logger()
router = APIRouter()


# ============================================================
# Helpers
# ============================================================

def _get_or_create_conversation(request: ChatRequest) -> tuple:
    """Returns (conv_id, conv_dict, error_msg_or_None)."""
    conv_id = request.conversation_id
    if conv_id:
        conv = get_conversation(conv_id)
        if not conv:
            return conv_id, None, "Conversation not found"
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
    return conv_id, conv, None


def _add_user_message(conv: dict, message: str, attachments: list = None):
    """Append user message to conversation."""
    user_msg = {
        "role": "user",
        "content": message,
        "timestamp": datetime.now().isoformat()
    }
    if attachments:
        # Convert Pydantic models to dicts if needed
        user_msg["attachments"] = [
            a.dict() if hasattr(a, 'dict') else a for a in attachments
        ]
    conv['messages'].append(user_msg)


def _save_assistant_message(conv: dict, response_text: str, sources: list = None,
                            summary_sources: list = None, low_confidence: bool = False,
                            used_summary_fallback: bool = False, confidence_score: float = 0.0,
                            followups: list = None):
    """Append assistant message and save conversation."""
    assistant_msg = {
        "role": "assistant",
        "content": response_text,
        "timestamp": datetime.now().isoformat(),
        "sources": sources or [],
        "summary_sources": summary_sources or [],
        "low_confidence": low_confidence,
        "used_summary_fallback": used_summary_fallback,
        "confidence_score": round(confidence_score, 3)
    }
    if followups:
        assistant_msg["followups"] = followups
    conv['messages'].append(assistant_msg)
    conv['updated_at'] = datetime.now().isoformat()
    save_conversation(conv)
    return assistant_msg


# ============================================================
# Agent response generator (streaming)
# ============================================================

async def generate_agent_response(request: ChatRequest, analysis) -> AsyncGenerator[str, None]:
    """Stream agent response as SSE events."""
    agent = get_agent_runner()
    chatbot = get_chatbot()

    if not agent:
        yield f"data: {json.dumps({'error': 'Agent not initialized'})}\n\n"
        return

    # Get or create conversation
    conv_id, conv, error = _get_or_create_conversation(request)
    if error:
        yield f"data: {json.dumps({'error': error})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'conversation_id', 'id': conv_id})}\n\n"

    _add_user_message(conv, request.message, request.attachments)

    # Extract images from attachments
    images = []
    if request.attachments:
        for att in request.attachments:
            if att.type == "image":
                base64_data = get_image_base64(att.url)
                if base64_data:
                    images.append(base64_data)

    # Build history for agent context
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in conv['messages'][:-1]  # exclude the message we just added
    ]

    # Synchronize chatbot history
    chatbot.conversation_history = history.copy()

    yield f"data: {json.dumps({'type': 'progress', 'step': 'thinking', 'message': 'Agent reasoning...'})}\n\n"

    # Use appropriate model based on mode
    agent_model = request.model or (
        get_config().llm_model_strong if request.mode == "reflexion" else get_config().llm_model
    )

    # Run agent stream
    response_text = ""
    sources = []
    summary_sources = []

    # Resolve persona
    persona = get_persona(request.agent_id)
    persona_prompt = persona.system_prompt_override

    for event in agent.run_stream(request.message, history=history, analysis=analysis, model=agent_model, images=images if images else None, persona_prompt=persona_prompt, allowed_tools=list(persona.allowed_tools) if persona.allowed_tools else None):
        event_type = event["type"]

        if event_type == "start":
            continue

        elif event_type == "thinking":
            # Just wait...
            yield f"data: {json.dumps({'type': 'progress', 'step': 'thinking', 'message': 'Analyse en cours...'})}\n\n"

        elif event_type == "thought":
            thought_text = event.get('content', '')
            one_liner = thought_text.split('\n')[0].strip()
            if len(one_liner) > 80:
                one_liner = one_liner[:77] + "..."
            yield f"data: {json.dumps({'type': 'progress', 'step': 'thinking', 'message': one_liner})}\n\n"

        elif event_type == "action":
            tool = event.get("tool", "")
            action_input = event.get("input", "")
            tool_messages = {
                "search_conversations": f"Recherche de '{action_input[:30]}...' dans les conversations",
                "get_contact_stats": f"Analyse des statistiques de {action_input}",
                "get_participants": "Récupération de la liste des participants",
                "get_todays_date": "Vérification de la date du jour",
            }
            msg = tool_messages.get(tool, f"Utilisation de l'outil {tool}...")
            yield f"data: {json.dumps({'type': 'progress', 'step': 'search', 'message': msg})}\n\n"

        elif event_type == "observation":
            yield f"data: {json.dumps({'type': 'progress', 'step': 'documents', 'message': 'Lecture des résultats...'})}\n\n"

        elif event_type == "final":
            response_text = event["answer"]
            sources = event.get("sources", [])
            summary_sources = event.get("summary_sources", [])

        elif event_type == "max_steps":
            response_text = event.get("message", "Maximum d'étapes atteint.")
            sources = event.get("sources", [])
            summary_sources = event.get("summary_sources", [])

        elif event_type == "error":
            response_text = f"Erreur: {event['message']}"
            yield f"data: {json.dumps({'type': 'chunk', 'content': response_text})}\n\n"
            _save_assistant_message(conv, response_text)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        await asyncio.sleep(0)

    # Send sources
    if sources or summary_sources:
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'summary_sources': summary_sources})}\n\n"

    # Stream the final answer
    if response_text:
        # Filter PII
        response_text = chatbot.filter_pii(response_text)
        yield f"data: {json.dumps({'type': 'chunk', 'content': response_text})}\n\n"

    # Generate follow-up questions
    yield f"data: {json.dumps({'type': 'progress', 'step': 'followups', 'message': 'Preparing suggestions...'})}\n\n"
    
    followups = []
    if response_text:
        try:
            followups = await run_sync(chatbot.generate_followup_questions, request.message, response_text, request.model)
        except Exception as e:
            logger.warning(f"Followup generation error: {e}")

    if followups:
        yield f"data: {json.dumps({'type': 'followups', 'questions': followups})}\n\n"

    # Save conversation
    context = agent.tools.get_last_context()
    _save_assistant_message(
        conv, response_text, sources, summary_sources,
        low_confidence=context.low_confidence if context else False,
        used_summary_fallback=context.used_summary_fallback if context else False,
        confidence_score=context.max_confidence_score if context else 0.0,
        followups=followups
    )

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ============================================================
# Direct response generator (fast-path, streaming)
# ============================================================

async def generate_direct_response(request: ChatRequest, analysis) -> AsyncGenerator[str, None]:
    """Stream direct retrieval response as SSE events (fast-path)."""
    retriever = get_retriever()
    chatbot = get_chatbot()

    # Get or create conversation
    conv_id, conv, error = _get_or_create_conversation(request)
    if error:
        yield f"data: {json.dumps({'error': error})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'conversation_id', 'id': conv_id})}\n\n"

    _add_user_message(conv, request.message, request.attachments)

    # Extract images from attachments
    images = []
    if request.attachments:
        for att in request.attachments:
            if att.type == "image":
                base64_data = get_image_base64(att.url)
                if base64_data:
                    images.append(base64_data)

    # Synchronize chatbot history with current conversation
    chatbot.conversation_history = [
        {"role": m["role"], "content": m["content"]}
        for m in conv['messages'][:-1]
    ]

    # Progress: Search step
    yield f"data: {json.dumps({'type': 'progress', 'step': 'search', 'message': 'Analyzing question...'})}\n\n"

    # Analysis parameters
    dyn_top_k = analysis.top_k
    dyn_reranking = analysis.use_reranking
    dyn_expand = analysis.expand_context
    search_query = analysis.rewritten_query

    intent_label = analysis.intent or 'info'
    yield f"data: {json.dumps({'type': 'progress', 'step': 'search', 'message': f'Searching ({intent_label})...'})}\n\n"

    # Handle broad vs strict person filtering
    p_filter = request.participant_filter
    a_person = request.about_person
    
    # If the UI sends a participant and asks for broad search, we move it to about_person
    if request.use_about_person and p_filter:
        a_person = p_filter
        p_filter = None

    # Dates
    final_date_start = request.date_start or analysis.date_start
    final_date_end = request.date_end or analysis.date_end

    context = await run_sync(
        retriever.retrieve,
        search_query,
        p_filter,
        a_person,
        request.group_filter,
        request.year_filter,
        final_date_start,
        final_date_end,
        dyn_top_k,
        dyn_reranking,
        request.use_hybrid,
        dyn_expand
    )

    # Smart Fallback: If rewritten query yields poor results, try original query
    if (context.low_confidence or not context.has_results) and search_query != request.message:
        yield f"data: {json.dumps({'type': 'progress', 'step': 'search', 'message': 'Broadening search (Smart Fallback)...'})}\n\n"

        fallback_context = await run_sync(
            retriever.retrieve,
            request.message,
            p_filter,
            a_person,
            request.group_filter,
            request.year_filter,
            final_date_start,
            final_date_end,
            dyn_top_k,
            dyn_reranking,
            request.use_hybrid,
            dyn_expand
        )
        # If fallback is better, replace
        if fallback_context.max_confidence_score > context.max_confidence_score:
            context = fallback_context
            yield f"data: {json.dumps({'type': 'progress', 'step': 'search', 'message': 'Better results found.'})}\n\n"

    # Send sources with chunk_id and preview
    sources = []
    summary_sources = []

    if context.results:
        yield f"data: {json.dumps({'type': 'progress', 'step': 'documents', 'message': f'Reading {len(context.results)} documents...', 'count': len(context.results)})}\n\n"

        for r in context.results:
            sources.append({
                "rank": r.rank,
                "chunk_id": r.chunk.chunk_id,
                "file": r.chunk.file_source,
                "participants": r.chunk.participants,
                "date_start": r.chunk.date_start[:10],
                "date_end": r.chunk.date_end[:10],
                "score": round(r.final_score, 2),
                "expanded": r.is_expanded,
                "preview": (r.chunk.narrative_summary or r.chunk.summary or r.chunk.content[:200])[:200]
            })

    # Add summary sources if fallback was used
    if context.used_summary_fallback and context.summary_results:
        for sr in context.summary_results:
            summary = sr.summary
            summary_sources.append({
                "type": "summary",
                "level": sr.level,
                "summary_id": summary.summary_id,
                "participants": summary.participants,
                "period": getattr(summary, 'period', None) or f"{summary.date_start[:10]} - {summary.date_end[:10]}",
                "score": round(sr.score, 2),
                "preview": summary.summary[:200]
            })

    if sources or summary_sources:
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'summary_sources': summary_sources})}\n\n"

    # Check for low confidence - skip LLM call if confidence is too low AND no summaries
    if (context.low_confidence and not context.used_summary_fallback) or not context.has_results:
        response_text = "I couldn't find relevant information in the conversations to answer this question. Could you rephrase or be more specific?"
        yield f"data: {json.dumps({'type': 'chunk', 'content': response_text})}\n\n"
    else:
        # Progress: Generating step
        yield f"data: {json.dumps({'type': 'progress', 'step': 'generating', 'message': 'Generating response...'})}\n\n"

        # Stream response
        response_text = ""
        # Use appropriate model based on mode
        chat_model = request.model or (
            get_config().llm_model_strong if request.mode == "reflexion" else get_config().llm_model_fast
        )
        
        # Resolve persona
        persona = get_persona(request.agent_id)
        persona_prompt = persona.system_prompt_override

        for chunk in chatbot.chat_stream(request.message, context.formatted_context, model=chat_model, images=images if images else None, persona_prompt=persona_prompt):
            response_text += chunk
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            await asyncio.sleep(0)  # Allow other tasks to run

        # Filter PII from final response
        response_text = chatbot.filter_pii(response_text)

    # Generate follow-up questions
    yield f"data: {json.dumps({'type': 'progress', 'step': 'followups', 'message': 'Preparing suggestions...'})}\n\n"

    followups = []
    if response_text and not context.low_confidence:
        try:
            followups = await run_sync(chatbot.generate_followup_questions, request.message, response_text, request.model)
        except Exception as e:
            logger.warning(f"Followup generation error: {e}")

    if followups:
        yield f"data: {json.dumps({'type': 'followups', 'questions': followups})}\n\n"

    # Save conversation
    _save_assistant_message(
        conv, response_text, sources, summary_sources,
        low_confidence=context.low_confidence,
        used_summary_fallback=context.used_summary_fallback,
        confidence_score=context.max_confidence_score,
        followups=followups
    )

    # Trigger compaction if necessary and inform frontend
    if len(conv['messages']) > 10:
        yield f"data: {json.dumps({'type': 'progress', 'step': 'compacting', 'message': 'Optimizing memory...'})}\n\n"
        chatbot._update_history(request.message, response_text, skip_add=True)

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ============================================================
# Endpoints
# ============================================================

@router.post("/chat")
async def chat(request: ChatRequest):
    """Send a message and get a response (non-streaming)."""
    retriever = get_retriever()
    chatbot = get_chatbot()
    query_analyzer = get_query_analyzer()
    agent = get_agent_runner()

    if not retriever or not chatbot:
        raise HTTPException(status_code=503, detail="RAG not initialized")

    # Omni-Analysis
    analysis = await run_sync(query_analyzer.analyze, request.message, chatbot.conversation_history)


    if should_use_agent(analysis, request.mode) and agent:
        # Agent path
        conv_id, conv, error = _get_or_create_conversation(request)
        if error:
            raise HTTPException(status_code=404, detail=error)

        _add_user_message(conv, request.message, request.attachments)
        
        # Extract images from attachments
        images = []
        if request.attachments:
            for att in request.attachments:
                if att.type == "image":
                    base64_data = get_image_base64(att.url)
                    if base64_data:
                        images.append(base64_data)

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in conv['messages'][:-1]
        ]

        # Use stronger model for agent if mode is reflexion
        agent_model = request.model or (
            get_config().llm_model_strong if request.mode == "reflexion" else get_config().llm_model
        )
        
        # Resolve persona
        persona = get_persona(request.agent_id)
        persona_prompt = persona.system_prompt_override

        result = await run_sync(agent.run, request.message, history, analysis, model=agent_model, images=images if images else None, persona_prompt=persona_prompt, allowed_tools=list(persona.allowed_tools) if persona.allowed_tools else None)
        response_text = chatbot.filter_pii(result.answer)

        context = agent.tools.get_last_context()
        assistant_msg = _save_assistant_message(
            conv, response_text, result.sources, result.summary_sources,
            low_confidence=context.low_confidence if context else False,
            used_summary_fallback=context.used_summary_fallback if context else False,
            confidence_score=context.max_confidence_score if context else 0.0
        )

        return {
            "conversation_id": conv_id,
            "message": assistant_msg,
            "sources": result.sources
        }

    # Fast-path: direct retrieval (original flow)
    conv_id, conv, error = _get_or_create_conversation(request)
    if error:
        raise HTTPException(status_code=404, detail=error)

    _add_user_message(conv, request.message, request.attachments)

    # Extract images from attachments
    images = []
    if request.attachments:
        for att in request.attachments:
            if att.type == "image":
                base64_data = get_image_base64(att.url)
                if base64_data:
                    images.append(base64_data)

    dyn_top_k = analysis.top_k
    dyn_reranking = analysis.use_reranking
    dyn_expand = analysis.expand_context
    search_query = analysis.rewritten_query

    final_date_start = request.date_start or analysis.date_start
    final_date_end = request.date_end or analysis.date_end

    context = await run_sync(
        retriever.retrieve,
        search_query,
        request.participant_filter,
        request.about_person,
        request.group_filter,
        request.year_filter,
        final_date_start,
        final_date_end,
        dyn_top_k,
        dyn_reranking,
        request.use_hybrid,
        dyn_expand
    )

    # Smart Fallback
    if (context.low_confidence or not context.has_results) and search_query != request.message:
        fallback_context = await run_sync(
            retriever.retrieve,
            request.message,
            request.participant_filter,
            request.about_person,
            request.group_filter,
            request.year_filter,
            final_date_start,
            final_date_end,
            dyn_top_k,
            dyn_reranking,
            request.use_hybrid,
            dyn_expand
        )
        if fallback_context.max_confidence_score > context.max_confidence_score:
            context = fallback_context

    # Generate response
    response_text = ""
    # Use appropriate model based on mode
    chat_model = request.model or (
        get_config().llm_model_strong if request.mode == "reflexion" else get_config().llm_model_fast
    )
    
    # Resolve persona for non-streaming path
    persona = get_persona(request.agent_id)
    persona_prompt = persona.system_prompt_override

    for chunk in chatbot.chat_stream(request.message, context.formatted_context, model=chat_model, images=images if images else None, persona_prompt=persona_prompt):
        response_text += chunk

    # Format sources
    sources = []
    if context.results:
        for r in context.results:
            sources.append({
                "rank": r.rank,
                "file": r.chunk.file_source,
                "participants": r.chunk.participants,
                "date_start": r.chunk.date_start[:10],
                "date_end": r.chunk.date_end[:10],
                "score": round(r.final_score, 2),
                "expanded": r.is_expanded
            })

    assistant_msg = _save_assistant_message(
        conv, response_text, sources,
        low_confidence=context.low_confidence,
        used_summary_fallback=context.used_summary_fallback,
        confidence_score=context.max_confidence_score
    )

    return {
        "conversation_id": conv_id,
        "message": assistant_msg,
        "sources": sources
    }


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Send a message and get a streaming response."""
    retriever = get_retriever()
    chatbot = get_chatbot()
    query_analyzer = get_query_analyzer()

    if not retriever or not chatbot:
        raise HTTPException(status_code=503, detail="RAG not initialized")

    logger.info(f"📨 Chat stream request: '{request.message}'")
    if request.group_filter:
        logger.info(f"👥 Group filter received: '{request.group_filter}' (Not yet implemented in retrieval)")

    # Omni-Analysis
    analysis = await run_sync(query_analyzer.analyze, request.message, chatbot.conversation_history)


    logger.info(f"🎯 Analysis result: mode={analysis.mode}, intent={analysis.intent}")

    # Binary routing
    if should_use_agent(analysis, request.mode):
        logger.info(f"🤖 Routing to AGENT for: '{request.message}' (mode={request.mode})")
        return StreamingResponse(
            generate_agent_response(request, analysis),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

    logger.info(f"⚡ Using FAST-PATH (direct retrieval) for: '{request.message}' (mode={request.mode})")
    return StreamingResponse(
        generate_direct_response(request, analysis),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
