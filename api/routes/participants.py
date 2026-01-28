"""
Participants and chunks routes.
"""
from fastapi import APIRouter, HTTPException

from api.dependencies import get_components

router = APIRouter()


@router.get("/participants")
async def list_participants():
    """List all participants for filtering."""
    components = get_components()
    if not components or 'metadata_store' not in components:
        return []

    participants = components['metadata_store'].get_all_participants()
    return [{"name": name, "count": count} for name, count in participants[:50]]


@router.get("/chunks/{chunk_id}")
async def get_chunk_content(chunk_id: str):
    """Get full chunk content for source detail modal."""
    components = get_components()
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
