import os
import uuid
import shutil
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from api.models import FileAttachment
from rag_pipeline.core.logger import get_logger

logger = get_logger()
router = APIRouter()

UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "txt", "doc", "docx"}

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/upload", response_model=List[FileAttachment])
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload multiple files and return their attachments metadata."""
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 files allowed")
    
    attachments = []
    for file in files:
        file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
        if file_ext not in ALLOWED_EXTENSIONS:
            logger.warning(f"File extension not allowed: {file_ext}")
            # continue # Skip or raise? User asked for 5 images/files. 
        
        file_id = str(uuid.uuid4())
        filename = f"{file_id}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Determine type
            file_type = "image" if file_ext in {"png", "jpg", "jpeg", "gif"} else "document"
            
            attachments.append(FileAttachment(
                id=file_id,
                name=file.filename,
                type=file_type,
                url=f"/api/uploads/{filename}",
                size=os.path.getsize(file_path)
            ))
        except Exception as e:
            logger.error(f"Error saving file {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Could not save file {file.filename}")
        finally:
            file.file.close()
            
    return attachments
