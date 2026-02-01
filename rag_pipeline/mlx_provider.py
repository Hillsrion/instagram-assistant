import sys
from typing import Optional, List, Dict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MlxProvider:
    """
    Provider for running LLMs locally using MLX (Apple Silicon).
    optimized for high-throughput batch processing (prefill).
    """
    
    _model = None
    _tokenizer = None
    _model_path = None

    def __init__(self, model_path: str = "mlx-community/Ministral-3-8B-Instruct-2512-4bit"):
        self.model_path = model_path
        self._ensure_model_loaded()

    def _ensure_model_loaded(self):
        """Loads the model if it's not already loaded."""
        if MlxProvider._model is None:
            try:
                from mlx_lm import load
                logger.info(f"Loading MLX model: {self.model_path}...")
                MlxProvider._model, MlxProvider._tokenizer = load(self.model_path)
                logger.info("MLX model loaded successfully.")
            except ImportError:
                logger.error("mlx_lm not installed. Please run `pip install mlx-lm`")
                raise
            except Exception as e:
                logger.error(f"Failed to load MLX model: {e}")
                raise

    def generate(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.1) -> str:
        """
        Generates text based on the prompt.
        
        Args:
            prompt: The input prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            
        Returns:
            The generated text.
        """
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler
        
        if MlxProvider._model is None:
            self._ensure_model_loaded()

        sampler = make_sampler(temp=temperature)

        response = generate(
            MlxProvider._model,
            MlxProvider._tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            verbose=False,
            sampler=sampler
        )
        return response

    def generate_chat(self, messages: List[Dict[str, str]], max_tokens: int = 2048, temperature: float = 0.1) -> str:
        """
        Generates text from a list of chat messages.
        """
        if MlxProvider._tokenizer is None:
             self._ensure_model_loaded()
             
        prompt = MlxProvider._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        return self.generate(prompt, max_tokens, temperature)
