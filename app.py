#!/usr/bin/env python3
"""
Instagram Conversations Assistant - Web Application
FastAPI backend with modern chat interface.
"""
import sys
import json
import uuid
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, AsyncGenerator
from contextlib import asynccontextmanager

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

# RAG imports
from rag_pipeline.config import Config
from rag_pipeline.advanced_retriever import create_advanced_retriever
from rag_pipeline.chat import ChatBot


# ============================================================
# Models
# ============================================================

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    sources: Optional[List[dict]] = None


class Conversation(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[Message] = []


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    # Model selection
    model: Optional[str] = None
    # Filters
    participant_filter: Optional[str] = None
    year_filter: Optional[int] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    # Options
    use_reranking: bool = True
    use_hybrid: bool = True
    expand_context: bool = True


class ConversationCreate(BaseModel):
    title: Optional[str] = None


# ============================================================
# Storage (simple JSON file)
# ============================================================

CONVERSATIONS_FILE = Path("rag_data/conversations.json")


def load_conversations() -> dict:
    """Load all conversations from file."""
    if not CONVERSATIONS_FILE.exists():
        return {}
    with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_conversations(conversations: dict):
    """Save all conversations to file."""
    CONVERSATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(conversations, f, ensure_ascii=False, indent=2)


def get_conversation(conv_id: str) -> Optional[dict]:
    """Get a single conversation by ID."""
    conversations = load_conversations()
    return conversations.get(conv_id)


def save_conversation(conv: dict):
    """Save a single conversation."""
    conversations = load_conversations()
    conversations[conv['id']] = conv
    save_conversations(conversations)


def delete_conversation(conv_id: str) -> bool:
    """Delete a conversation."""
    conversations = load_conversations()
    if conv_id in conversations:
        del conversations[conv_id]
        save_conversations(conversations)
        return True
    return False


# ============================================================
# Global state
# ============================================================

retriever = None
chatbot = None
config = None
components = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize RAG components on startup."""
    global retriever, chatbot, config, components

    print("=" * 60)
    print("Instagram Conversations Assistant")
    print("=" * 60)
    print()

    config = Config()

    # Check if index exists
    if not (config.vector_store_path / "index.faiss").exists():
        print("Index FAISS non trouvé.")
        print("Lancez d'abord: python3 setup_rag_batch.py")
        print()
        print("L'application démarre en mode limité...")
        yield
        return

    print("Chargement des composants RAG...")
    try:
        retriever, components = create_advanced_retriever(
            config,
            enable_reranking=True,
            enable_bm25=True,
            enable_metadata=True,
            enable_summaries=True
        )
        chatbot = ChatBot(config)
        print(f"Index chargé: {components['vector_store'].size} chunks")
        print()
        print(f"Application prête sur http://localhost:8000")
        print()
    except Exception as e:
        print(f"Erreur lors du chargement: {e}")

    yield

    # Cleanup
    if components and 'metadata_store' in components:
        components['metadata_store'].close()


# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title="Instagram Conversations Assistant",
    lifespan=lifespan
)

# ============================================================
# API Routes
# ============================================================


@app.get("/api/status")
async def get_status():
    """Get system status."""
    return {
        "ready": retriever is not None,
        "chunks_count": components['vector_store'].size if components else 0,
        "has_bm25": components and 'bm25_index' in components,
        "has_reranker": components and 'reranker' in components,
        "has_metadata": components and 'metadata_store' in components,
        "has_summaries": components and 'summary_store' in components,
    }


@app.get("/api/ollama/models")
async def list_ollama_models():
    """List available Ollama models and return the default model."""
    if not config:
        raise HTTPException(status_code=503, detail="Config not initialized")

    try:
        import requests
        response = requests.get(
            f"{config.ollama_url}/api/tags",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        models = []
        for model in data.get("models", []):
            models.append({
                "name": model["name"],
                "size": model.get("size", 0),
                "modified_at": model.get("modified_at", "")
            })

        return {
            "models": models,
            "default_model": config.llm_model
        }

    except Exception as e:
        print(f"Error listing Ollama models: {e}")
        raise HTTPException(status_code=503, detail="Cannot reach Ollama")


@app.get("/api/conversations")
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


@app.post("/api/conversations")
async def create_conversation(data: ConversationCreate):
    """Create a new conversation."""
    conv_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    conv = {
        "id": conv_id,
        "title": data.title or "Nouvelle conversation",
        "created_at": now,
        "updated_at": now,
        "messages": []
    }

    save_conversation(conv)
    return conv


@app.get("/api/conversations/{conv_id}")
async def get_conversation_detail(conv_id: str):
    """Get a conversation with all messages."""
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation_endpoint(conv_id: str):
    """Delete a conversation."""
    if delete_conversation(conv_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Conversation not found")


@app.patch("/api/conversations/{conv_id}")
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


@app.get("/api/participants")
async def list_participants():
    """List all participants for filtering."""
    if not components or 'metadata_store' not in components:
        return []

    participants = components['metadata_store'].get_all_participants()
    return [{"name": name, "count": count} for name, count in participants[:50]]


@app.get("/api/chunks/{chunk_id}")
async def get_chunk_content(chunk_id: str):
    """Get full chunk content for source detail modal."""
    if not components or 'vector_store' not in components:
        raise HTTPException(status_code=503, detail="Vector store not available")

    vector_store = components['vector_store']

    # Find chunk by ID
    for chunk in vector_store.chunks:
        if chunk.chunk_id == chunk_id:
            return {
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "summary": chunk.narrative_summary or chunk.summary,
                "participants": chunk.participants,
                "date_start": chunk.date_start,
                "date_end": chunk.date_end,
                "file_source": chunk.file_source,
                "message_count": chunk.message_count,
                "hypothetical_questions": chunk.hypothetical_questions or []
            }

    raise HTTPException(status_code=404, detail="Chunk not found")


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Send a message and get a response (non-streaming)."""
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

    # Retrieve context
    context = retriever.retrieve(
        query=request.message,
        participant_filter=request.participant_filter,
        year_filter=request.year_filter,
        date_start=request.date_start,
        date_end=request.date_end,
        use_reranking=request.use_reranking,
        use_hybrid=request.use_hybrid,
        expand_context=request.expand_context
    )

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


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """Send a message and get a streaming response."""
    if not retriever or not chatbot:
        raise HTTPException(status_code=503, detail="RAG not initialized")

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

        # Progress: Search step
        yield f"data: {json.dumps({'type': 'progress', 'step': 'search', 'message': 'Recherche en cours...'})}\n\n"

        context = retriever.retrieve(
            query=request.message,
            participant_filter=request.participant_filter,
            year_filter=request.year_filter,
            date_start=request.date_start,
            date_end=request.date_end,
            use_reranking=request.use_reranking,
            use_hybrid=request.use_hybrid,
            expand_context=request.expand_context
        )

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

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
