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
    
    # Class-level registry to avoid reloading models in the same process
    _registry = {}

    def __init__(self, model_path: str = "mlx-community/Ministral-3-8B-Instruct-2512-4bit"):
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        self._ensure_model_loaded()

    def _ensure_model_loaded(self):
        """Loads the model into the registry if not already present."""
        if self.model_path in MlxProvider._registry:
            self.model, self.tokenizer = MlxProvider._registry[self.model_path]
            return

        try:
            from mlx_lm import load
            logger.info(f"Loading MLX model: {self.model_path}...")
            
            try:
                self.model, self.tokenizer = load(self.model_path)
            except ValueError as e:
                # Workaround for "Tokenizer class TokenizersBackend does not exist" error
                if "TokenizersBackend" in str(e):
                    logger.warning(f"Detected problematic tokenizer class in {self.model_path}. Applying workaround...")
                    self.model, self.tokenizer = load(
                        self.model_path, 
                        tokenizer_config={"tokenizer_class": "PreTrainedTokenizerFast"}
                    )
                else:
                    raise

            MlxProvider._registry[self.model_path] = (self.model, self.tokenizer)
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
        
        if self.model is None:
            self._ensure_model_loaded()

        sampler = make_sampler(temp=temperature)

        response = generate(
            self.model,
            self.tokenizer,
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
        if self.tokenizer is None:
             self._ensure_model_loaded()
             
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        return self.generate(prompt, max_tokens, temperature)
