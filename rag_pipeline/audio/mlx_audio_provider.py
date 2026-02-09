
import sys
import logging
import base64
from pathlib import Path
from typing import Optional, List, Dict, Any

from rag_pipeline.core.config import default_config

# Configure logging
logger = logging.getLogger(__name__)

class MlxAudioProvider:
    """
    Provider for running Voxtral audio transcription models locally using MLX.
    Uses mlx_vlm to handle the multimodal input.
    """
    
    # Class-level registry to avoid reloading models in the same process
    _registry = {}

    def __init__(self, model_path: str = None):
        self.model_path = model_path or default_config.mlx_audio_model
        self.model = None
        self.processor = None
        self._ensure_model_loaded()

    def _ensure_model_loaded(self):
        """voxmlx handles loading internally during the first call."""
        pass

    def transcribe(self, audio_path: Path, language: str = "fr") -> Optional[str]:
        """
        Transcribes an audio file using the local MLX model via voxmlx.
        Handles format conversion via ffmpeg if necessary.
        
        Args:
            audio_path: Path to the audio file (supports .mp4, .m4a, .aac, etc.)
            language: Target language code (default: fr)
            
        Returns:
            Transcription text if successful, None otherwise.
        """
        import subprocess
        import tempfile
        import os
        import shlex
        
        try:
            if not audio_path.exists():
                logger.warning(f"Audio file not found: {audio_path}")
                return None
            
            # Standardizing all audio to WAV via FFmpeg for voxmlx compatibility
            temp_wav = None
            try:
                fd, temp_wav = tempfile.mkstemp(suffix='.wav')
                os.close(fd)
                
                print(f"   🔄 Standardizing {audio_path.name}...")
                # Convert to wav (16kHz mono is safe for most speech models)
                cmd = [
                    'ffmpeg', '-y', '-i', str(audio_path),
                    '-ar', '16000', '-ac', '1',
                    temp_wav
                ]
                
                # Use subprocess with a timeout to avoid hanging
                subprocess.run(
                    cmd, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL,
                    check=True,
                    timeout=30
                )
                process_path = temp_wav
            except subprocess.TimeoutExpired:
                logger.error(f"FFmpeg timed out for {audio_path.name}")
                if temp_wav and os.path.exists(temp_wav):
                    os.remove(temp_wav)
                return None
            except Exception as e:
                logger.error(f"FFmpeg processing failed for {audio_path.name}: {e}")
                if temp_wav and os.path.exists(temp_wav):
                    os.remove(temp_wav)
                return None

            try:
                from voxmlx import transcribe
                print(f"   🎙️  Transcribing {audio_path.name}...")
                text = transcribe(
                    process_path,
                    model_path=self.model_path
                )
                return text.strip() if text else None
            except Exception as e:
                logger.error(f"VoxMLX failed for {audio_path.name}: {e}")
                return None
            finally:
                if temp_wav and os.path.exists(temp_wav):
                    try:
                        os.remove(temp_wav)
                    except:
                        pass
                    
        except Exception as e:
            logger.error(f"Transcription failed for {audio_path.name}: {e}")
            return None

        except Exception as e:
            logger.error(f"Transcription failed for {audio_path.name}: {e}")
            return None
