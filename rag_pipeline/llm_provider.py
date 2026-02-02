"""
LLM Provider Abstraction for Evaluations

Provides a unified interface for calling different LLM providers (Ollama, MLX)
during evaluation runs. Includes GPU/CPU sharding support for enrichment tasks.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import requests
from rag_pipeline.config import Config
from rag_pipeline.mlx_provider import MlxProvider


class LLMProvider(ABC):
    """Base class for LLM providers used in evaluations."""

    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
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

    def __init__(self, config: Config, model: str, url: str = None):
        self.config = config
        self.model = model
        self.url = url or config.ollama_url

    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
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
        timeout = kwargs.get("timeout", 180)

        response = requests.post(
            f"{self.url}/api/chat",
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


class ShardedOllamaProvider(LLMProvider):
    """Sharded Ollama provider that routes between GPU and CPU instances based on message count."""

    def __init__(self, config: Config, model: str, gpu_url: str, cpu_url: str, threshold: int = 20):
        """
        Initialize sharded provider with health checks.

        Args:
            config: Application configuration
            model: Model name
            gpu_url: GPU Ollama instance URL
            cpu_url: CPU Ollama instance URL
            threshold: Message count threshold (>=threshold uses GPU, <threshold uses CPU)
        """
        self.config = config
        self.model = model
        self.gpu_url = gpu_url
        self.cpu_url = cpu_url
        self.threshold = threshold

        # Create provider instances
        self.gpu_provider = OllamaProvider(config, model, url=gpu_url)
        self.cpu_provider = OllamaProvider(config, model, url=cpu_url)

        # Statistics tracking
        self.stats = {
            "gpu_routed": 0,
            "cpu_routed": 0,
            "cpu_fallback": 0,
            "errors": 0
        }

        # Perform health checks
        self._check_health(gpu_url, "GPU")
        self._check_health(cpu_url, "CPU")

    def _check_health(self, url: str, label: str) -> None:
        """
        Ping Ollama instance to verify it's available.

        Args:
            url: Ollama instance URL
            label: Label for logging ("GPU" or "CPU")

        Raises:
            RuntimeError: If GPU instance is unavailable (fail-fast)
            Logs warning: If CPU instance is unavailable (will fallback)
        """
        try:
            response = requests.get(f"{url}/api/tags", timeout=5)
            response.raise_for_status()
            print(f"✓ {label} Ollama instance healthy at {url}")
        except Exception as e:
            error_msg = f"{label} Ollama instance unreachable at {url}: {e}"
            if label == "GPU":
                # Fail fast for GPU
                raise RuntimeError(
                    f"GPU Ollama instance unavailable at {url}.\n"
                    f"GPU must be available for sharded mode (fail-fast policy).\n"
                    f"Check if Ollama is running on GPU port."
                )
            else:
                # Warn for CPU (will fallback)
                print(f"⚠️  {error_msg}")
                print("    Small chunks will fallback to GPU")

    def generate(self, messages: List[Dict[str, str]], message_count: Optional[int] = None, **kwargs) -> str:
        """
        Route request to GPU or CPU based on message count.

        Args:
            messages: Chat messages
            message_count: Number of messages in chunk (determines routing)
            **kwargs: Additional options passed to provider

        Returns:
            Generated text from appropriate provider
        """
        # Default to threshold if message_count not provided
        if message_count is None:
            message_count = self.threshold

        # Determine routing
        use_gpu = message_count >= self.threshold

        try:
            if use_gpu:
                self.stats["gpu_routed"] += 1
                return self.gpu_provider.generate(messages, **kwargs)
            else:
                # Try CPU first
                try:
                    self.stats["cpu_routed"] += 1
                    return self.cpu_provider.generate(messages, **kwargs)
                except Exception as e:
                    # CPU down, fallback to GPU
                    print(f"⚠️  CPU Ollama instance unreachable: {e}")
                    print("    Routing small chunk to GPU (fallback)")
                    self.stats["cpu_fallback"] += 1
                    return self.gpu_provider.generate(messages, **kwargs)
        except Exception as e:
            self.stats["errors"] += 1
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Return routing statistics and calculated metrics."""
        total_routed = self.stats["gpu_routed"] + self.stats["cpu_routed"]
        gpu_utilization = (
            (self.stats["gpu_routed"] / total_routed * 100) if total_routed > 0 else 0
        )

        return {
            **self.stats,
            "gpu_utilization_percent": round(gpu_utilization, 1),
            "total_routed": total_routed
        }


class MLXProviderWrapper(LLMProvider):
    """MLX provider wrapper for evaluations."""

    def __init__(self, config: Config, model: str):
        self.config = config
        self.model = model
        self.mlx = MlxProvider(model_path=model)

    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Call MLX provider."""
        max_tokens = kwargs.get("max_tokens", 2048)
        temperature = kwargs.get("temperature", 0.1)
        return self.mlx.generate_chat(messages, max_tokens, temperature)


def create_provider(
    config: Config,
    model: str,
    provider_type: str = "ollama",
    enable_sharding: bool = False,
    gpu_url: Optional[str] = None,
    cpu_url: Optional[str] = None,
    threshold: int = 20
) -> LLMProvider:
    """
    Factory function to create appropriate provider.

    Args:
        config: Application configuration
        model: Model name/path
        provider_type: "ollama" or "mlx"
        enable_sharding: If True (and provider_type is "ollama"), use sharded provider
        gpu_url: GPU instance URL (required if enable_sharding=True)
        cpu_url: CPU instance URL (required if enable_sharding=True)
        threshold: Message count threshold for GPU routing (default: 20)

    Returns:
        LLMProvider instance
    """
    if provider_type == "mlx":
        return MLXProviderWrapper(config, model)
    elif enable_sharding and gpu_url and cpu_url:
        return ShardedOllamaProvider(config, model, gpu_url, cpu_url, threshold)
    else:
        return OllamaProvider(config, model)
