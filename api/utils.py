import base64
import os
from typing import Optional
from rag_pipeline.core.logger import get_logger

logger = get_logger()

def get_image_base64(file_url: str) -> Optional[str]:
    """
    Reads an image file and returns its base64 encoded string.
    
    Args:
        file_url: URL of the file (e.g., /api/uploads/filename)
        
    Returns:
        Base64 string or None if error
    """
    # Extract filename from URL (remove /api/uploads/ or /uploads/)
    filename = file_url.split("/")[-1]
    file_path = os.path.join("uploads", filename)
    
    if not os.path.exists(file_path):
        logger.error(f"File not found for base64 encoding: {file_path}")
        return None
        
    try:
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded_string
    except Exception as e:
        logger.error(f"Error encoding image {file_path}: {e}")
        return None
