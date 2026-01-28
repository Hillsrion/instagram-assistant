"""
Analytics routes.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException

from api.dependencies import get_analytics

router = APIRouter()


@router.get("/message_count")
async def get_message_count(
    participant: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    conversation_id: Optional[str] = None
):
    """
    Get message count with optional filters.

    Query params:
    - participant: Filter by participant name (partial match)
    - start: Start date (ISO format)
    - end: End date (ISO format)
    - conversation_id: Filter by conversation ID
    """
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=503, detail="Analytics not initialized")

    try:
        count = analytics.count_messages(
            participant=participant,
            date_start=start,
            date_end=end,
            conversation_id=conversation_id
        )
        return {"count": count}
    except Exception as e:
        print(f"Error getting message count: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/participant_stats")
async def get_participant_stats():
    """Get statistics for all participants."""
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=503, detail="Analytics not initialized")

    try:
        stats = analytics.get_participant_stats()
        return {"participants": stats}
    except Exception as e:
        print(f"Error getting participant stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation_timeline")
async def get_conversation_timeline(participant: str):
    """Get timeline of conversations with a specific participant."""
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=503, detail="Analytics not initialized")

    if not participant:
        raise HTTPException(status_code=400, detail="participant parameter required")

    try:
        timeline = analytics.get_conversation_timeline(participant)
        return {"timeline": timeline}
    except Exception as e:
        print(f"Error getting conversation timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topic_participants")
async def get_topic_participants(topic: str):
    """Get list of participants who discussed a specific topic."""
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=503, detail="Analytics not initialized")

    if not topic:
        raise HTTPException(status_code=400, detail="topic parameter required")

    try:
        participants = analytics.get_topic_participants(topic)
        return {"participants": participants}
    except Exception as e:
        print(f"Error getting topic participants: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation_participants")
async def get_conversation_participants(conversation_id: str):
    """Get all participants in a conversation with their message counts."""
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=503, detail="Analytics not initialized")

    if not conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id parameter required")

    try:
        participants = analytics.get_participants_by_conversation(conversation_id)
        return {"participants": participants}
    except Exception as e:
        print(f"Error getting conversation participants: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/date_range")
async def get_date_range():
    """Get the overall date range of all conversations."""
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=503, detail="Analytics not initialized")

    try:
        start, end = analytics.get_date_range()
        return {"date_start": start, "date_end": end}
    except Exception as e:
        print(f"Error getting date range: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview")
async def get_analytics_overview():
    """Get overall statistics about all conversations."""
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=503, detail="Analytics not initialized")

    try:
        stats = analytics.get_conversation_stats()
        return stats
    except Exception as e:
        print(f"Error getting analytics overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monthly_timeline")
async def get_monthly_timeline(participant: Optional[str] = None):
    """Get message counts grouped by month."""
    analytics = get_analytics()
    if not analytics:
        raise HTTPException(status_code=503, detail="Analytics not initialized")

    try:
        timeline = analytics.get_message_count_by_month(participant)
        return {"timeline": timeline}
    except Exception as e:
        print(f"Error getting monthly timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))
