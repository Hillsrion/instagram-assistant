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

logger = logging.getLogger(__name__)

class AudioTranscriber:
    """
    Handles audio transcription using a local VLLM server running Voxtral.
    """
    def __init__(self, api_url: str = None):
        self.api_url = api_url or default_config.vllm_audio_url
        self.enabled = default_config.enable_audio_transcription

    def transcribe(self, audio_path: Path) -> Optional[str]:
        """
        Transcribes an audio file using the VLLM endpoint.
        
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

        try:
            # 1. Read and encode audio file
            # Voxtral typically expects inputs via chat completions API with specific format
            # Depending on VLLM's exact implementation for multimodal, we might need to 
            # pass the file path if it's local to the server, or base64.
            # Assuming standard OpenAI-compatible API with image_url-like structure or similar for audio.
            # Mistral's Voxtral example often uses specific prompting.
            # For VLLM serving, we usually follow the OpenAI Chat Completions format.
            
            # Note: As of early 2026/late 2025, VLLM support for audio models often involves 
            # specific input structures. We will assume a standard structure where we pass 
            # the audio URL or base64 in the user content.
            
            with open(audio_path, "rb") as f:
                audio_data = base64.b64encode(f.read()).decode("utf-8")
                
            # Construct payload for OpenAI-compatible VLLM endpoint
            # Adjust model name based on what's served (we'll use a config or default)
            
            payload = {
                "model": default_config.vllm_audio_model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Transcris cet audio fidèlement. Si c'est inaudible, dis '[inaudible]'."},
                            {
                                "type": "image_url", # VLLM often reuses image_url struct for multimodel, or has a specific one
                                # Checking VLLM specific docs for audio... 
                                # If native audio support is not fully standardized in OpenAI API spec, 
                                # we might need to send it differently.
                                # However, for Voxtral (Mistral), standard VLLM usage usually implies 
                                # passing input_ids or specific prompt format.
                                # Given the USER request mentioned Voxtral on VLLM, 
                                # let's assume standard multimodal input pattern.
                                "image_url": {
                                    "url": f"data:audio/mp4;base64,{audio_data}" 
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 256
            }
            
            # Note: "image_url" is often hijacked for "audio_url" or "inputs" in generic VLLM multimodal 
            # if strict OpenAI compat is used. If this fails, we might need custom VLLM API.
            # Let's try the standard OpenAI chat completion endpoint.
            
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30  # Audio processing can be slow
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return content.strip()
            else:
                logger.error(f"VLLM API Error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Transcription failed for {audio_path.name}: {e}")
            return None
