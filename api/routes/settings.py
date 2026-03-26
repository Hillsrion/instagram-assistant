from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal
from api.storage import load_settings, save_settings
from rag_pipeline.core.config import default_config
from rag_pipeline.core.prompts import AVAILABLE_TONES

router = APIRouter(prefix="/settings", tags=["settings"])

class SettingsModel(BaseModel):
    developerMode: bool
    agentTone: Literal["Professionnel", "Amical", "Concise"]
    globalInstructions: str
    interfaceTheme: Literal["Clair", "Sombre", "Système"]
    ownUsername: str


@router.get("")
async def get_settings():
    """Retrieve current settings."""
    try:
        return load_settings()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def update_settings(settings: SettingsModel):
    """Update settings and reload config."""
    try:
        settings_dict = settings.model_dump()
        save_settings(settings_dict)
        
        # Reload global config
        default_config.load_settings()
        
        return {"status": "success", "message": "Settings updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tones")
async def get_tones():
    """Get available agent tones."""
    return list(AVAILABLE_TONES.keys())
