"""
Chat routes - main chat and streaming endpoints.
"""
import json
import uuid
import asyncio
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.models import ChatRequest
from api.storage import get_conversation, save_conversation
from api.dependencies import (
    get_retriever,
    get_chatbot,
    get_query_analyzer
)
from api.handlers import handle_computational_query, handle_discovery_query
from rag_pipeline.logger import get_logger

logger = get_logger()
router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest):
    """Send a message and get a response (non-streaming)."""
    retriever = get_retriever()
    chatbot = get_chatbot()
    query_analyzer = get_query_analyzer()
    
    if not retriever or not chatbot:
        raise HTTPException(status_code=503, detail="RAG not initialized")

    # Get or create conversation
    conv_id = request.conversation_id
    if conv_id:
        conv = get_conversation(conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        # Create new conversation
        conv_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        conv = {
            "id": conv_id,
            "title": request.message[:50] + ("..." if len(request.message) > 50 else ""),
            "created_at": now,
            "updated_at": now,
            "messages": []
        }

    # Add user message
    user_msg = {
        "role": "user",
        "content": request.message,
        "timestamp": datetime.now().isoformat()
    }
    conv['messages'].append(user_msg)

    # Omni-Analyse (Rewrite + Intent + Dates) en un seul appel LLM
    analysis = query_analyzer.analyze(request.message, chatbot.conversation_history)
    
    dyn_top_k = analysis.top_k
    dyn_reranking = analysis.use_reranking
    dyn_expand = analysis.expand_context
    search_query = analysis.rewritten_query

    # On utilise les dates extraites par l'analyzer si présentes
    final_date_start = request.date_start or analysis.date_start
    final_date_end = request.date_end or analysis.date_end

    # Retrieve context
    context = retriever.retrieve(
        query=search_query,
        participant_filter=request.participant_filter,
        year_filter=request.year_filter,
        date_start=final_date_start,
        date_end=final_date_end,
        top_k=dyn_top_k,
        use_reranking=dyn_reranking,
        use_hybrid=request.use_hybrid,
        expand_context=dyn_expand
    )

    # Smart Fallback: Si la requête réécrite donne peu de résultats, on tente la requête originale
    if (context.low_confidence or not context.has_results) and search_query != request.message:
        print(f"⚠️ Low confidence ({context.max_confidence_score:.2f}). Attempting fallback with original query.")
        
        fallback_context = retriever.retrieve(
            query=request.message,
            participant_filter=request.participant_filter,
            year_filter=request.year_filter,
            date_start=final_date_start,
            date_end=final_date_end,
            top_k=dyn_top_k,
            use_reranking=dyn_reranking,
            use_hybrid=request.use_hybrid,
            expand_context=dyn_expand
        )
        
        # Si le fallback est meilleur ou si l'original n'avait rien, on remplace
        if fallback_context.max_confidence_score > context.max_confidence_score:
            print(f"✅ Fallback successful: score {context.max_confidence_score:.2f} -> {fallback_context.max_confidence_score:.2f}")
            context = fallback_context

    # Generate response
    response_text = ""
    for chunk in chatbot.chat_stream(request.message, context.formatted_context, model=request.model):
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

    # Add assistant message
    assistant_msg = {
        "role": "assistant",
        "content": response_text,
        "timestamp": datetime.now().isoformat(),
        "sources": sources
    }
    conv['messages'].append(assistant_msg)
    conv['updated_at'] = datetime.now().isoformat()

    save_conversation(conv)

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

    # Omni-Analyse (Rewrite + Intent + Dates + Mode) en un seul appel LLM
    analysis = query_analyzer.analyze(request.message, chatbot.conversation_history)

    logger.info(f"🎯 Analysis result: mode={analysis.mode}, intent={analysis.intent}")

    # Intelligent Routing based on LLM decision
    if analysis.mode == "analytics":
        query_lower = request.message.lower()
        
        # Define explicit keywords for routing
        discovery_keywords = ["liste", "qui", "participants", "tous les", "show all", "list"]
        computational_keywords = ["combien", "nombre", "count", "statistiques", "stats"]
        
        is_discovery = any(k in query_lower for k in discovery_keywords)
        is_computational = any(k in query_lower for k in computational_keywords)
        
        if is_discovery:
            logger.info(f"⚠️ Routing to DISCOVERY mode for: '{request.message}'")
            return StreamingResponse(
                handle_discovery_query(request),
                media_type="text/event-stream"
            )
        elif is_computational:
            logger.info(f"⚠️ Routing to COMPUTATIONAL mode for: '{request.message}'")
            return StreamingResponse(
                handle_computational_query(request),
                media_type="text/event-stream"
            )
        else:
            logger.warning(f"⚠️ Analytics mode proposed by LLM but no keywords matched. Fallback to RETRIEVAL.")
            # Fall through to retrieval logic below

    logger.info(f"🔄 Using RETRIEVAL flow")

    # Default: retrieval flow
    async def generate() -> AsyncGenerator[str, None]:
        # Get or create conversation
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

        # Send conversation ID first
        yield f"data: {json.dumps({'type': 'conversation_id', 'id': conv_id})}\n\n"

        # Add user message
        user_msg = {
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat()
        }
        conv['messages'].append(user_msg)
        
        # Synchroniser l'historique du chatbot avec la conversation actuelle
        chatbot.conversation_history = [
            {"role": m["role"], "content": m["content"]} 
            for m in conv['messages'][:-1]
        ]

        # Progress: Search step
        yield f"data: {json.dumps({'type': 'progress', 'step': 'search', 'message': 'Analyse de la question...'})}\n\n"
        
        # L'analyse a déjà été faite pour le routing, on réutilise ses paramètres
        dyn_top_k = analysis.top_k
        dyn_reranking = analysis.use_reranking
        dyn_expand = analysis.expand_context
        search_query = analysis.rewritten_query
        
        intent_label = analysis.intent or 'info'
        yield f"data: {json.dumps({'type': 'progress', 'step': 'search', 'message': f'Recherche ({intent_label})...'})}\n\n"

        # Dates
        final_date_start = request.date_start or analysis.date_start
        final_date_end = request.date_end or analysis.date_end

        context = retriever.retrieve(
            query=search_query,
            participant_filter=request.participant_filter,
            year_filter=request.year_filter,
            date_start=final_date_start,
            date_end=final_date_end,
            top_k=dyn_top_k,
            use_reranking=dyn_reranking,
            use_hybrid=request.use_hybrid,
            expand_context=dyn_expand
        )

        # Smart Fallback: Si la requête réécrite donne peu de résultats, on tente la requête originale
        if (context.low_confidence or not context.has_results) and search_query != request.message:
            yield f"data: {json.dumps({'type': 'progress', 'step': 'search', 'message': 'Recherche élargie (Smart Fallback)...'})}\n\n"
            
            fallback_context = retriever.retrieve(
                query=request.message,
                participant_filter=request.participant_filter,
                year_filter=request.year_filter,
                date_start=final_date_start,
                date_end=final_date_end,
                top_k=dyn_top_k,
                use_reranking=dyn_reranking,
                use_hybrid=request.use_hybrid,
                expand_context=dyn_expand
            )
            
            # Si le fallback est meilleur, on remplace
            if fallback_context.max_confidence_score > context.max_confidence_score:
                context = fallback_context
                yield f"data: {json.dumps({'type': 'progress', 'step': 'search', 'message': 'Meilleurs résultats trouvés.'})}\n\n"

        # Send sources with chunk_id and preview
        sources = []
        summary_sources = []

        if context.results:
            yield f"data: {json.dumps({'type': 'progress', 'step': 'documents', 'message': f'Lecture de {len(context.results)} documents...', 'count': len(context.results)})}\n\n"

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
            response_text = "Je n'ai pas trouve d'information pertinente dans les conversations pour repondre a cette question. Pouvez-vous reformuler ou preciser votre demande ?"
            yield f"data: {json.dumps({'type': 'chunk', 'content': response_text})}\n\n"
        else:
            # Progress: Generating step
            yield f"data: {json.dumps({'type': 'progress', 'step': 'generating', 'message': 'Generation de la reponse...'})}\n\n"

            # Stream response
            response_text = ""
            for chunk in chatbot.chat_stream(request.message, context.formatted_context, model=request.model):
                response_text += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                await asyncio.sleep(0)  # Allow other tasks to run

            # Filter PII from final response
            response_text = chatbot.filter_pii(response_text)

        # Generate follow-up questions
        yield f"data: {json.dumps({'type': 'progress', 'step': 'followups', 'message': 'Preparation des suggestions...'})}\n\n"

        followups = []
        if response_text and not context.low_confidence:
            try:
                followups = chatbot.generate_followup_questions(request.message, response_text, model=request.model)
            except Exception as e:
                print(f"Followup generation error: {e}")

        if followups:
            yield f"data: {json.dumps({'type': 'followups', 'questions': followups})}\n\n"

        # Save conversation
        assistant_msg = {
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.now().isoformat(),
            "sources": sources,
            "summary_sources": summary_sources,
            "low_confidence": context.low_confidence,
            "used_summary_fallback": context.used_summary_fallback,
            "confidence_score": round(context.max_confidence_score, 3)
        }
        conv['messages'].append(assistant_msg)
        conv['updated_at'] = datetime.now().isoformat()
        save_conversation(conv)

        # Déclencher le compactage si nécessaire et informer le front
        if len(conv['messages']) > 10:
            yield f"data: {json.dumps({'type': 'progress', 'step': 'compacting', 'message': 'Optimisation de la mémoire...'})}\n\n"
            chatbot._update_history(request.message, response_text, skip_add=True)
            # Si un compactage a eu lieu, on pourrait vouloir sauvegarder le résumé
            # mais pour l'instant il reste en mémoire vive du chatbot global.

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
