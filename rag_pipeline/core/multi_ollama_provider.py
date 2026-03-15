"""
Multi-Endpoint Ollama Provider with Load Balancing.

Distributes LLM requests across multiple Ollama instances for parallel processing.
Supports round-robin load balancing, health checking, and automatic failover.
"""
import requests
import threading
from queue import Queue
from typing import List, Dict, Any, Optional
from rag_pipeline.core.config import Config


class MultiOllamaProvider:
    """Ollama provider that distributes requests across multiple endpoints.
    
    Features:
    - Round-robin load balancing
    - Per-endpoint health checking
    - Automatic failover on endpoint failure
    - Thread-safe endpoint cycling
    - Request statistics tracking
    """

    def __init__(self, config: Config, model: str, endpoints: List[str] = None):
        """
        Initialize multi-endpoint provider.
        
        Args:
            config: Application configuration
            model: Model name to use
            endpoints: List of Ollama endpoint URLs. If None, uses config.ollama_endpoints
        """
        self.config = config
        self.model = model
        self.endpoints = endpoints or getattr(config, 'ollama_endpoints', [config.ollama_url])
        
        # Ensure we have at least one endpoint
        if not self.endpoints:
            self.endpoints = [config.ollama_url]
        
        # Thread-safe endpoint cycling using a queue
        self._endpoint_queue = Queue()
        for endpoint in self.endpoints:
            self._endpoint_queue.put(endpoint)
        
        # Health status and statistics
        self._health_status: Dict[str, bool] = {}
        self._request_stats: Dict[str, int] = {ep: 0 for ep in self.endpoints}
        self._lock = threading.Lock()
        
        # Track if health check has been performed
        self._health_checked = False

    def _get_next_endpoint(self) -> str:
        """Get next endpoint in round-robin fashion (thread-safe)."""
        endpoint = self._endpoint_queue.get()
        self._endpoint_queue.put(endpoint)  # Put it back at the end
        return endpoint

    def check_health(self) -> Dict[str, bool]:
        """Check health of all endpoints.
        
        Returns:
            Dict mapping endpoint URL to health status (True = healthy)
        """
        for endpoint in self.endpoints:
            try:
                response = requests.get(
                    f"{endpoint}/api/tags",
                    timeout=5
                )
                self._health_status[endpoint] = response.status_code == 200
            except Exception:
                self._health_status[endpoint] = False
        
        self._health_checked = True
        
        # Log health status
        healthy_count = sum(1 for v in self._health_status.values() if v)
        print(f"🔍 Endpoint health: {healthy_count}/{len(self.endpoints)} healthy")
        for endpoint, healthy in self._health_status.items():
            status = "✅" if healthy else "❌"
            print(f"   {status} {endpoint}")
        
        return self._health_status

    def get_stats(self) -> Dict[str, int]:
        """Get request statistics per endpoint."""
        with self._lock:
            return dict(self._request_stats)

    def _call_endpoint(self, endpoint: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """Make a request to a specific endpoint."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.1),
                "top_p": kwargs.get("top_p", 0.9),
                "num_predict": kwargs.get("max_tokens", 1024),
                "num_ctx": kwargs.get("num_ctx", self.config.num_ctx)
            }
        }
        
        # Add format if specified (string or dict schema)
        if kwargs.get("format"):
            payload["format"] = kwargs.get("format")
            
        timeout = kwargs.get("timeout", 300)

        response = requests.post(
            f"{endpoint}/api/chat",
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        
        # Update stats
        with self._lock:
            self._request_stats[endpoint] = self._request_stats.get(endpoint, 0) + 1
        
        return response.json()["message"]["content"]

    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Generate text from chat messages, distributing across endpoints.

        Args:
            messages: List of chat messages with 'role' and 'content' keys
            **kwargs: Provider-specific options (temperature, max_tokens, etc.)

        Returns:
            Generated text content
            
        Raises:
            Exception: If all endpoints fail
        """
        # Perform initial health check if not done
        if not self._health_checked and len(self.endpoints) > 1:
            self.check_health()
        
        # Try endpoints in order, with failover
        tried_endpoints = set()
        last_error = None
        
        for _ in range(len(self.endpoints)):
            endpoint = self._get_next_endpoint()
            
            # Skip if already tried
            if endpoint in tried_endpoints:
                continue
            tried_endpoints.add(endpoint)
            
            # Skip if known to be unhealthy (but allow fallback to unhealthy if all healthy fail)
            if self._health_checked and not self._health_status.get(endpoint, True):
                if len(tried_endpoints) < len(self.endpoints):
                    continue
            
            try:
                return self._call_endpoint(endpoint, messages, **kwargs)
            except Exception as e:
                last_error = e
                print(f"⚠️ Endpoint {endpoint} failed: {e}")
                # Mark as unhealthy
                self._health_status[endpoint] = False
                continue
        
        # All endpoints failed
        raise Exception(f"All {len(self.endpoints)} endpoints failed. Last error: {last_error}")

    def print_stats(self):
        """Print request distribution statistics."""
        stats = self.get_stats()
        total = sum(stats.values())
        if total == 0:
            return
        
        print("\n" + "=" * 60)
        print("📊 MULTI-ENDPOINT DISTRIBUTION")
        print("=" * 60)
        for endpoint, count in stats.items():
            pct = 100 * count / total if total > 0 else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            print(f"  {endpoint}")
            print(f"    {bar} {count} requests ({pct:.1f}%)")
        print(f"{'─' * 60}")
        print(f"  Total: {total} requests")
        print("=" * 60 + "\n")
