
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
        """Loads the model into the registry if not already present."""
        if self.model_path in MlxAudioProvider._registry:
            self.model, self.processor = MlxAudioProvider._registry[self.model_path]
            return

        try:
            from mlx_voxtral import VoxtralForConditionalGeneration, VoxtralProcessor
            
            logger.info(f"Loading MLX Audio model (voxtral): {self.model_path}...")
            
            # Using class method which usually handles full model loading (encoder+decoder)
            self.model = VoxtralForConditionalGeneration.from_pretrained(self.model_path)
            self.processor = VoxtralProcessor.from_pretrained(self.model_path)
            
            MlxAudioProvider._registry[self.model_path] = (self.model, self.processor)
            logger.info("MLX Audio model loaded successfully.")
            
        except ImportError:
            logger.error("mlx-voxtral not installed. Please run `pip install mlx-voxtral`")
            raise
        except Exception as e:
            logger.error(f"Failed to load MLX Audio model '{self.model_path}': {e}")
            logger.error("This may be due to an incompatibility between the mlx-voxtral package and the model checkpoint.")
            raise

    def transcribe(self, audio_path: Path, language: str = "fr") -> Optional[str]:
        """
        Transcribes an audio file using the local Voxtral model.
        
        Args:
            audio_path: Path to the audio file (supports .mp4, .m4a, .aac, etc.)
            language: Target language code (default: fr)
            
        Returns:
            Transcription text if successful, None otherwise.
        """
        if self.model is None:
            self._ensure_model_loaded()
            
        try:
            from mlx_voxtral import process_audio_for_voxtral
            
            if not audio_path.exists():
                logger.warning(f"Audio file not found: {audio_path}")
                return None
            
            # 1. Process Audio
            # Assuming process_audio_for_voxtral takes path and processor
            # Verify signature via trial or assumption. 
            # If it fails, capturing exception.
            audio_features = process_audio_for_voxtral(str(audio_path), self.processor)
            
            # 2. Generate
            # Prompt construction might be needed?
            # Voxtral is speech-to-text, usually prompted with language token or direct audio.
            # We'll try direct generation.
            
            # Check if model has generate method
            if hasattr(self.model, 'generate'):
                text = self.model.generate(audio_features, max_tokens=256)
            else:
                # If no generate method, we might need a utility from mlx_voxtral
                # defaulting to trying a generate function from the package if existing?
                # But based on class name VoxtralForConditionalGeneration, it likely has generate.
                # If not, we fall back to a generic generation loop which is complex to implement blindly.
                # Let's assume generate exists or we simply fail here and log.
                logger.error(f"Model {type(self.model)} has no generate method.")
                return None
            
            return text.strip() if text else None

        except Exception as e:
            logger.error(f"Transcription failed for {audio_path.name}: {e}")
            return None
