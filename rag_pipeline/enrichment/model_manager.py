"""
Model management for enrichment routing.
Handles model loading strategies (dual-load, on-demand), 
switching, and routing statistics.
"""
import time
import psutil
import requests
from typing import Dict, Optional, Any, List

class EnrichmentModelManager:
    """Manages LLM models for enrichment routing."""

    def __init__(self, config, provider: str = "ollama"):
        self.config = config
        self.provider = provider
        
        # Models
        self.model = self.config.llm_model
        self.light_model = getattr(self.config, 'llm_light_model', 'ministral-3:3b')
        
        # Strategies
        self.loading_strategy = getattr(self.config, 'model_loading_strategy', 'dual')
        self.current_loaded_model = None
        
        # Statistics
        self.stats = {
            "simple": 0,
            "medium": 0,
            "complex": 0,
            "model_switches": 0,
            "total_switch_time_ms": 0,
        }

    def preload_models(self):
        """Preload both light and strong models (dual-load strategy)."""
        if self.provider != "ollama" or self.loading_strategy != "dual":
            return

        try:
            available_ram_gb = psutil.virtual_memory().available / (1024 ** 3)
            min_required = getattr(self.config, 'min_ram_gb_for_dual', 10.0)

            if available_ram_gb < min_required:
                print(f"⚠️ Low RAM ({available_ram_gb:.1f}GB < {min_required}GB). "
                      f"Consider using --model-strategy on-demand")
                return

            print(f"🔄 Preloading models (dual-load strategy)...")
            # Warm-up: force Ollama to load both models
            for model_name in [self.light_model, self.model]:
                try:
                    self.call_ollama("test", model=model_name)
                    print(f"  ✅ {model_name} loaded")
                except Exception as e:
                    print(f"  ⚠️ Failed to preload {model_name}: {e}")
            self.current_loaded_model = self.model  # Track which is currently "warm"
        except Exception as e:
            print(f"⚠️ Failed to preload models: {e}")

    def ensure_model_loaded(self, model_name: str):
        """Load a model on-demand if using on-demand strategy."""
        if self.loading_strategy == "dual":
            return  # Both models already preloaded
        if self.provider == "mlx":
            return  # MLX doesn't support hot-swapping easily

        if self.current_loaded_model != model_name:
            start = time.time()
            try:
                # Warm-up call to load the model
                self.call_ollama("test", model=model_name)
                load_time_ms = (time.time() - start) * 1000
                self.stats["model_switches"] += 1
                self.stats["total_switch_time_ms"] += load_time_ms
                self.current_loaded_model = model_name
            except Exception as e:
                print(f"⚠️ Failed to load {model_name}: {e}")

    def call_ollama(self, prompt: str, model: str) -> str:
        """Call Ollama chat API, using multi-endpoint if configured."""
        try:
            # Use multi-endpoint provider if load balancing is enabled
            use_lb = getattr(self.config, 'use_load_balancing', False)
            endpoints = getattr(self.config, 'ollama_endpoints', [self.config.ollama_url])
            if use_lb and len(endpoints) > 1:
                # Use MultiOllamaProvider for load balancing
                if not hasattr(self, '_multi_provider') or self._multi_provider is None:
                    from rag_pipeline.core.multi_ollama_provider import MultiOllamaProvider
                    self._multi_provider = MultiOllamaProvider(self.config, model, endpoints)
                    # Update model if different
                elif self._multi_provider.model != model:
                    self._multi_provider.model = model
                
                messages = [{"role": "user", "content": prompt}]
                return self._multi_provider.generate(
                    messages,
                    temperature=0.0,
                    num_ctx=self.config.num_ctx
                )
            else:
                # Single endpoint - use direct request
                url = f"{self.config.ollama_url}/api/chat"
                num_ctx = self.config.num_ctx
                
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                        "num_ctx": num_ctx
                    }
                }
                response = requests.post(url, json=payload, timeout=300)
                response.raise_for_status()
                return response.json()["message"]["content"]
        except Exception as e:
            raise e

    def update_stats(self, category: str):
        """Update routing statistics."""
        if category in self.stats:
            self.stats[category] += 1

    def print_routing_stats(self):
        """Print routing statistics summary."""
        total = (self.stats["simple"] +
                 self.stats["medium"] +
                 self.stats["complex"])

        if total == 0:
            return

        print("\n" + "="*60)
        print("📊 COMPLEXITY ROUTING STATISTICS")
        print("="*60)
        print(f"Simple chunks:   {self.stats['simple']:6} ({100*self.stats['simple']/total:.1f}%)")
        print(f"Medium chunks:   {self.stats['medium']:6} ({100*self.stats['medium']/total:.1f}%)")
        print(f"Complex chunks:  {self.stats['complex']:6} ({100*self.stats['complex']/total:.1f}%)")
        print(f"{'─'*60}")
        print(f"Model switches:  {self.stats['model_switches']}")
        if self.stats['model_switches'] > 0:
            avg_switch_time = self.stats['total_switch_time_ms'] / self.stats['model_switches']
            print(f"Avg switch time: {avg_switch_time:.0f}ms")
        print("="*60 + "\n")
