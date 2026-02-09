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


from rag_pipeline.core.config import default_config
from rag_pipeline.audio.audio_cache import AudioCache
from rag_pipeline.audio.mlx_audio_provider import MlxAudioProvider

logger = logging.getLogger(__name__)

class AudioTranscriber:
    """
    Handles audio transcription using a local MLX Voxtral model.
    Integrates with AudioCache to avoid redundant processing.
    """
    def __init__(self):
        self.enabled = default_config.enable_audio_transcription
        self.cache = AudioCache() if self.enabled else None
        self.provider = None

    def _ensure_provider(self):
        """Lazy loads the MLX audio provider."""
        if self.provider is None and self.enabled:
            self.provider = MlxAudioProvider()

    def transcribe(self, audio_path: Path) -> Optional[str]:
        """
        Transcribes an audio file using the local MLX model.
        Checks cache first.
        
        Args:
            audio_path: Absolute path to the audio file (mp4, m4a, aac, etc.)
            
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
            self._ensure_provider()
            content = self.provider.transcribe(audio_path, language=default_config.voxtral_language)
            
            if content:
                # 3. Save to Cache
                self.cache.set(audio_path, content, model=default_config.mlx_audio_model)
                self.cache.save()
                print(f"   ✅ Transcribed: {audio_path.name} ({len(content)} chars)")
                return content
            else:
                return None
                
        except Exception as e:
            logger.error(f"Transcription failed for {audio_path.name}: {e}")
            return None
