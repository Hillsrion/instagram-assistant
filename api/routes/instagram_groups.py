import uuid
from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException
from api.models import (
    InstagramThread, 
    SourceGroup, 
    SourceGroupUpdate,
    SourceGroupBulkUpdate
)
from api.dependencies import get_components
from api.storage_groups import (
    load_source_groups,
    save_source_group,
    delete_source_group,
    get_source_group
)
from rag_pipeline.core.logger import get_logger

logger = get_logger()
router = APIRouter()

@router.get("/instagram/threads", response_model=List[InstagramThread])
async def list_instagram_threads():
    """List all unique Instagram threads from the summary index."""
    components = get_components()
    if not components or 'summary_store' not in components:
        return []

    try:
        summary_store = components['summary_store']
        threads = []
        
        for summary in summary_store.conversation_summaries:
            # Defensive field extraction
            date_start = (getattr(summary, 'date_start', "") or "")[:10]
            date_end = (getattr(summary, 'date_end', "") or "")[:10]
            
            try:
                thread = InstagramThread(
                    id=summary.conversation_id,
                    participants=summary.participants or [],
                    summary=getattr(summary, 'summary', "") or "",
                    message_count=getattr(summary, 'total_messages', 0) or 0,
                    date_range=f"{date_start} - {date_end}"
                )
                threads.append(thread)
            except Exception as model_err:
                logger.error(f"Error creating InstagramThread model for {summary.conversation_id}: {model_err}")
                continue
        
        return sorted(threads, key=lambda x: x.id)
    except Exception as e:
        logger.error(f"Unhandled error in list_instagram_threads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/instagram/groups", response_model=List[SourceGroup])
async def list_source_groups():
    """List all user-defined Instagram source groups."""
    groups = load_source_groups()
    return sorted(groups.values(), key=lambda x: x['updated_at'], reverse=True)

@router.post("/instagram/groups", response_model=SourceGroup)
async def create_source_group(data: SourceGroupUpdate):
    """Create a new source group."""
    group_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    
    group = {
        "id": group_id,
        "title": data.title,
        "thread_ids": [],
        "created_at": now,
        "updated_at": now
    }
    
    save_source_group(group)
    return group

@router.delete("/instagram/groups/{group_id}")
async def delete_source_group_endpoint(group_id: str):
    """Delete a source group."""
    if delete_source_group(group_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Group not found")

@router.post("/instagram/groups/{group_id}/bulk")
async def bulk_update_source_group_threads(group_id: str, data: SourceGroupBulkUpdate):
    """Add or remove threads from a source group."""
    group = get_source_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    thread_ids = set(group.get("thread_ids", []))
    updated_count = 0
    
    for tid in data.thread_ids:
        if data.action == "add":
            if tid not in thread_ids:
                thread_ids.add(tid)
                updated_count += 1
        elif data.action == "remove":
            if tid in thread_ids:
                thread_ids.remove(tid)
                updated_count += 1
                
    if updated_count > 0:
        group["thread_ids"] = list(thread_ids)
        group["updated_at"] = datetime.now().isoformat()
        save_source_group(group)
        
    return {"status": "success", "updated_count": updated_count}
