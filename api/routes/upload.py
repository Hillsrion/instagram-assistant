from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import uuid
from pathlib import Path
import os
import zipfile

router = APIRouter()

TEMP_UPLOAD_DIR = Path("temp_uploads")
TEMP_UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("/onboarding/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Create a unique directory for this upload
        upload_id = str(uuid.uuid4())
        upload_dir = TEMP_UPLOAD_DIR / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / file.filename
        
        # Save the uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Check if it's a zip and extract
        if file.filename.endswith(".zip"):
            extract_dir = upload_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # Check structure: usually instagram export has "your_instagram_activity"
                # If specifically found, point to its parent or itself
                # For now, return the extract_dir as the source
                return {"path": str(extract_dir.absolute())}
            except zipfile.BadZipFile:
                 # If zip fails, just return the file path (though likely useless for the script)
                 pass

        # If it's a folder upload (not standard in single HTTP request), we usually get a zip
        # If the user uploads a single file (not zip), we return the directory
        return {"path": str(upload_dir.absolute())}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
