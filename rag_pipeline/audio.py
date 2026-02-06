"""
Audio Transcription Service.

Handles interaction with vllm/Voxtral model to transcribe audio files
found in Instagram exports.
"""
import base64
import requests
import logging
from pathlib import Path
from typing import Optional

from .config import default_config
from .audio_cache import AudioCache

logger = logging.getLogger(__name__)

class AudioTranscriber:
    """
    Handles audio transcription using a local VLLM server running Voxtral.
    Integrates with AudioCache to avoid redundant processing.
    """
    def __init__(self, api_url: str = None):
        self.api_url = api_url or default_config.vllm_audio_url
        self.enabled = default_config.enable_audio_transcription
        self.cache = AudioCache() if self.enabled else None

    def transcribe(self, audio_path: Path) -> Optional[str]:
        """
        Transcribes an audio file using the VLLM endpoint.
        Checks cache first.
        
        Args:
            audio_path: Absolute path to the audio file
            
        Returns:
            Transcription text if successful, None otherwise.
        """
        if not self.enabled:
            return None
            
        if not audio_path.exists():
            logger.warning(f"Audio file not found: {audio_path}")
            return None

        # 1. Check Cache
        cached_text = self.cache.get(audio_path)
        if cached_text:
            return cached_text

        try:
            # 2. Real Transcription
            with open(audio_path, "rb") as f:
                audio_data = base64.b64encode(f.read()).decode("utf-8")
                
            payload = {
                "model": default_config.vllm_audio_model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Transcris cet audio fidèlement. Si c'est inaudible, dis '[inaudible]'."},
                            {
                                "type": "image_url", 
                                "image_url": {
                                    "url": f"data:audio/mp4;base64,{audio_data}" 
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 1024
            }
            
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60  # Audio processing can be slow
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                
                # 3. Save to Cache
                self.cache.set(audio_path, content, model=default_config.vllm_audio_model_name)
                self.cache.save()
                
                return content
            else:
                logger.error(f"VLLM API Error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Transcription failed for {audio_path.name}: {e}")
            return None
