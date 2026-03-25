"""
LLM Provider Abstraction for Evaluations

Provides a unified interface for calling different LLM providers (Ollama, MLX)
during evaluation runs.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import requests
from rag_pipeline.core.config import Config
from rag_pipeline.core.mlx_provider import MlxProvider


class LLMProvider(ABC):
    """Base class for LLM providers used in evaluations."""

    @abstractmethod
    def generate(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Generate text from chat messages.

        Args:
            messages: List of chat messages with 'role' and 'content' keys
            **kwargs: Provider-specific options (temperature, max_tokens, etc.)

        Returns:
            Generated text content
        """
        pass


class OllamaProvider(LLMProvider):
    """Ollama HTTP API provider."""

    def __init__(self, config: Config, model: str):
        self.config = config
        self.model = model

    def generate(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Call Ollama HTTP API."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.1),
                "top_p": kwargs.get("top_p", 0.9),
                "num_predict": kwargs.get("max_tokens", 1024)
            }
        }
        
        # Add format if specified (string or dict schema)
        if kwargs.get("format"):
            payload["format"] = kwargs.get("format")
            
        timeout = kwargs.get("timeout", 300)

        response = requests.post(
            f"{self.config.ollama_url}/api/chat",
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


class MLXProviderWrapper(LLMProvider):
    """MLX provider wrapper for evaluations."""

    def __init__(self, config: Config, model: str):
        self.config = config
        self.model = model
        self.mlx = MlxProvider(model_path=model)

    def generate(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Call MLX provider."""
        max_tokens = kwargs.get("max_tokens", 2048)
        temperature = kwargs.get("temperature", 0.1)
        return self.mlx.generate_chat(messages, max_tokens, temperature)


def create_provider(config: Config, model: str, provider_type: str = "ollama") -> LLMProvider:
    """
    Factory function to create appropriate provider.

    Args:
        config: Application configuration
        model: Model name/path
        provider_type: "ollama" or "mlx"

    Returns:
        LLMProvider instance
    """
    if provider_type == "mlx":
        return MLXProviderWrapper(config, model)
    else:
        # Use multi-endpoint provider if load balancing is enabled
        use_lb = getattr(config, 'use_load_balancing', False)
        endpoints = getattr(config, 'ollama_endpoints', [config.ollama_url])
        if use_lb and len(endpoints) > 1:
            from rag_pipeline.core.multi_ollama_provider import MultiOllamaProvider
            return MultiOllamaProvider(config, model, endpoints)
        return OllamaProvider(config, model)
