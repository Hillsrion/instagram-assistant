from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import asyncio
import json
import shutil
import sys
import subprocess
from datetime import datetime

from ..jobs import manager, Job, JobStatus
from ..routes.conversations import get_conversations
from ..utils.dialogs import open_folder_dialog

router = APIRouter()

class ImportRequest(BaseModel):
    source_path: str

class FilterConfig(BaseModel):
    min_messages: int = 0
    start_date: Optional[str] = None # YYYY-MM-DD
    end_date: Optional[str] = None

class RagRequest(BaseModel):
    filter_config: Optional[FilterConfig] = None
    force_reset: bool = False

async def run_import_job(job: Job, source_path: str):
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Path not found: {source_path}")

    # 1. Prepare target
    target_dir = Path("instagram_conversations")
    target_dir.mkdir(exist_ok=True)
    
    # 2. Run instagram_to_text.py
    # We run it as a subprocess to capture output easily and isolate environment
    cmd = [sys.executable, "instagram_to_text.py", "--input", str(source), "--output", str(target_dir)]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    job.log(f"Running command: {' '.join(cmd)}")
    
    async def read_stream(stream, is_stderr=False):
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode().strip()
            if text:
                prefix = "[ERR] " if is_stderr else ""
                job.log(f"{prefix}{text}")

    await asyncio.gather(
        read_stream(process.stdout),
        read_stream(process.stderr, is_stderr=True)
    )
    
    await process.wait()
    
    if process.returncode != 0:
        raise Exception(f"Import process failed with code {process.returncode}")
        
    job.log("Import finished.")
    return True

async def run_rag_job(job: Job, filter_config: Optional[FilterConfig], force_reset: bool):
    # 1. Generate Allowlist if filters provided
    allowlist_file = None
    if filter_config:
        job.log("Applying filters...")
        # Get all conversations (reusing logic from existing endpoints or just listing)
        # For simplicity, we'll list files and parse headers or use the get_conversations logic?
        # Using get_conversations might be heavy if not async/optimized.
        # Let's just do a quick scan since we have the TXT files.
        
        conv_dir = Path("instagram_conversations")
        allowed_ids = []
        
        for f in conv_dir.glob("*.txt"):
            try:
                # Read first few lines for stats
                content = ""
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read(1024) # Read header
                    
                # Simple parsing
                msg_count = 0
                date_end = None
                
                if "Nombre de messages:" in content:
                    parts = content.split("Nombre de messages:")[1].split("\n")[0].strip()
                    try:
                        msg_count = int(parts)
                    except: pass
                    
                if msg_count < filter_config.min_messages:
                    continue

                # Date Filter: "Période: du YYYY-MM-DD au YYYY-MM-DD"
                if filter_config.start_date or filter_config.end_date:
                    if "Période:" in content:
                        period_line = content.split("Période:")[1].split("\n")[0].strip()
                        # Expected: "du 2020-01-01 au 2023-01-01"
                        if "au " in period_line:
                            last_date_str = period_line.split("au ")[1].strip()
                            try:
                                conv_end_date = datetime.strptime(last_date_str, "%Y-%m-%d")
                                
                                # Filter: Keep if conversation has activity AFTER start_date
                                if filter_config.start_date:
                                    filter_start = datetime.strptime(filter_config.start_date, "%Y-%m-%d")
                                    if conv_end_date < filter_start:
                                        continue
                                        
                                # Filter: Keep if conversation started BEFORE end_date (not implemented here, usually we care about recent activity)
                                # The user said "il y a eu un echange il y a moins de x temps" -> Recent activity.
                                # So checking the END date of the conversation against the filter START date is correct.
                                
                            except Exception as e:
                                job.log(f"Date parse error for {f.name}: {e}")
                
                allowed_ids.append(f.stem)
            except Exception as e:
                job.log(f"Skipping {f.name}: {e}")
                
        job.log(f"Filter kept {len(allowed_ids)} conversations.")
        
        # Save allowlist
        allowlist_path = Path("rag_data/allowlist.json")
        allowlist_path.parent.mkdir(exist_ok=True)
        with open(allowlist_path, 'w') as f:
            json.dump(allowed_ids, f)
        allowlist_file = allowlist_path

    # 2. Run setup_rag.py
    cmd = [sys.executable, "setup_rag.py"]
    if force_reset:
        cmd.append("--reset")
    if allowlist_file:
        cmd.extend(["--allowlist-file", str(allowlist_file)])
        
    # Force unbuffered output for python
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
        
    job.log(f"Starting RAG pipeline: {' '.join(cmd)}")
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )
    
    async def read_stream(stream, is_stderr=False):
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode().strip()
            if text:
                prefix = "[ERR] " if is_stderr else ""
                job.log(f"{prefix}{text}")
                
                # Update progress heuristic
                if "Step" in text and "/" in text:
                    # heuristic parsing "Step 1/8"
                    pass

    await asyncio.gather(
        read_stream(process.stdout),
        read_stream(process.stderr, is_stderr=True)
    )
    
    await process.wait()
    
    if process.returncode != 0:
        raise Exception(f"RAG process failed with code {process.returncode}")
        
    job.log("RAG Pipeline finished.")
    return True


@router.post("/onboarding/browse")
async def browse_folder():
    """Opens a native folder dialog on the server and returns the path."""
    # Run in a thread to not block the event loop
    path = await asyncio.to_thread(open_folder_dialog)
    if not path:
        return {"path": None}
    return {"path": path}


@router.post("/onboarding/import")
async def start_import(request: ImportRequest, background_tasks: BackgroundTasks):
    job = manager.create_job("import")
    background_tasks.add_task(job.run, run_import_job, request.source_path)
    return {"job_id": job.id}

@router.post("/onboarding/rag")
async def start_rag(request: RagRequest, background_tasks: BackgroundTasks):
    job = manager.create_job("rag")
    background_tasks.add_task(job.run, run_rag_job, request.filter_config, request.force_reset)
    return {"job_id": job.id}

@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_index = 0
        while True:
            # Check for new logs
            while last_index < len(job.logs):
                log_line = job.logs[last_index]
                yield f"data: {json.dumps({'type': 'log', 'content': log_line})}\\n\n"
                last_index += 1
            
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                yield f"data: {json.dumps({'type': 'status', 'status': job.status, 'result': job.result})}\\n\n"
                break
            
            # Wait for new logs or timeout
            try:
                await asyncio.wait_for(job._new_log_event.wait(), timeout=1.0)
                job._new_log_event.clear()
            except asyncio.TimeoutError:
                # Keep alive
                yield ": keep-alive\\n\\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/onboarding/conversations")
async def list_imported_conversations():
    """List conversations directly from the text files (lightweight)."""
    # Reuse simple parsing logic
    conv_dir = Path("instagram_conversations")
    if not conv_dir.exists():
        return []
    
    conversations = []
    for f in conv_dir.glob("*.txt"):
        try:
            stat = f.stat()
            # Basic parsing - improved: read first 20 lines
            details = {
                "id": f.stem,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "title": f.stem,
                "msg_count": 0,
                "date_range": "Unknown"
            }
            with open(f, 'r', encoding='utf-8') as file:
                head = [next(file) for _ in range(20)]
                for line in head:
                    if line.startswith("# Conversation Instagram avec"):
                        details["title"] = line.replace("# Conversation Instagram avec", "").strip()
                    if line.startswith("Nombre de messages:"):
                        try:
                            details["msg_count"] = int(line.split(":")[1].strip())
                        except:
                            pass
                    if line.startswith("Période:"):
                        details["date_range"] = line.replace("Période:", "").strip()
            conversations.append(details)
        except:
            continue
            
    # Sort by msg count desc
    conversations.sort(key=lambda x: x["msg_count"], reverse=True)
    return conversations
