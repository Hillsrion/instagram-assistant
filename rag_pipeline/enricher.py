"""
Chunk enricher using an LLM to generate narrative summaries
and hypothetical questions (advanced RAG techniques).

Supports complexity-based model routing: simple chunks → 3B model,
complex chunks → 8B model for faster indexing with acceptable quality.
"""
import json
import time
import requests
import psutil
import re
import traceback
from typing import List, Optional, Tuple, Dict
from .config import Config, default_config
from .chunker import Chunk
from .complexity_analyzer import ChunkComplexityAnalyzer
from .enrichment_log import EnrichmentLogger
from .json_utils import repair_and_load_json, parse_enrichment_data
from .prompts import ENRICH_PROMPT

class ChunkEnricher:
    """Uses an LLM (via Ollama or MLX) to enrich chunk metadata.

    Supports complexity-based routing:
    - Simple chunks → light model (3B)
    - Medium chunks → configurable
    - Complex chunks → strong model (8B)
    """

    def __init__(self, config: Config = None, provider: str = "ollama"):
        self.config = config or default_config
        self.provider = provider

        # Main model (fallback / strong model)
        self.model = self.config.llm_model
        self.mlx_provider = None

        # Complexity-based routing setup
        self.enable_routing = getattr(self.config, 'enable_complexity_routing', True)
        self.light_model = getattr(self.config, 'llm_light_model', 'ministral-3:3b')
        self.loading_strategy = getattr(self.config, 'model_loading_strategy', 'dual')
        self.force_model = getattr(self.config, 'force_model', None)
        self.current_loaded_model = None
        self.complexity_analyzer = ChunkComplexityAnalyzer(self.config) if self.enable_routing else None

        # Routing statistics
        self.routing_stats = {
            "simple": 0,
            "medium": 0,
            "complex": 0,
            "model_switches": 0,
            "total_switch_time_ms": 0,
        }

        # Enrichment logging
        self.enrichment_logger = EnrichmentLogger() if self.enable_routing else None

        if self.provider == "mlx":
            from .mlx_provider import MlxProvider
            # Use a default MLX model if config.llm_model looks like an Ollama model name
            # or use the one specified in config if it looks like a path/hf-repo
            mlx_model = "mlx-community/Ministral-3-8B-Instruct-2512-4bit"
            # If the config model contains '/' it's likely a HF repo, so use it.
            if "/" in self.model:
                mlx_model = self.model

            print(f"[Enricher] Loading MLX model: {mlx_model}")
            self.mlx_provider = MlxProvider(model_path=mlx_model)
        elif self.provider == "ollama" and self.enable_routing and self.loading_strategy == "dual":
            # Preload both models if using dual-load strategy
            self._preload_models() 
        
    def _preload_models(self):
        """Preload both light and strong models (dual-load strategy)."""
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
                    self._call_ollama("test", model=model_name)
                    print(f"  ✅ {model_name} loaded")
                except Exception as e:
                    print(f"  ⚠️ Failed to preload {model_name}: {e}")
            self.current_loaded_model = self.model  # Track which is currently "warm"
        except Exception as e:
            print(f"⚠️ Failed to preload models: {e}")

    def _ensure_model_loaded(self, model_name: str):
        """Load a model on-demand if using on-demand strategy."""
        if self.loading_strategy == "dual":
            return  # Both models already preloaded
        if self.provider == "mlx":
            return  # MLX doesn't support hot-swapping easily

        if self.current_loaded_model != model_name:
            start = time.time()
            try:
                # Warm-up call to load the model
                self._call_ollama("test", model=model_name)
                load_time_ms = (time.time() - start) * 1000
                self.routing_stats["model_switches"] += 1
                self.routing_stats["total_switch_time_ms"] += load_time_ms
                self.current_loaded_model = model_name
            except Exception as e:
                print(f"⚠️ Failed to load {model_name}: {e}")

    def _call_ollama(self, prompt: str, model: str) -> str:
        """Call Ollama chat API."""
        try:
            url = f"{self.config.ollama_url}/api/chat"
            # Context window size: larger for ministral, smaller for others if not specified
            num_ctx = self.config.num_ctx
            
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {
                    "temperature": 0.0,  # Deterministic for JSON
                    "num_ctx": num_ctx
                }
            }
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception as e:
            # Propagate to let caller handle retries/logging
            raise e

    def _call_mlx(self, prompt: str) -> str:
        """Call MLX provider."""
        if not self.mlx_provider:
             raise ValueError("MLX provider not initialized")
        
        messages = [{"role": "user", "content": prompt}]
        # Generate with default params or config derived
        return self.mlx_provider.generate_chat(messages, temperature=0.1)

    def _select_model_for_chunk(self, chunk: Chunk) -> str:
        """Select which model to use for a chunk based on complexity."""
        # If routing is disabled or forced, use the specified model
        if self.force_model:
            return self.force_model
        if not self.enable_routing:
            return self.model

        try:
            analysis = self.complexity_analyzer.analyze(chunk)

            # Route based on category
            if analysis.category == "simple":
                self.routing_stats["simple"] += 1
                return self.light_model
            elif analysis.category == "medium":
                self.routing_stats["medium"] += 1
                # Configurable: route medium to light or strong
                use_light = getattr(self.config, 'complexity_medium_uses_light', True)
                return self.light_model if use_light else self.model
            else:  # complex
                self.routing_stats["complex"] += 1
                return self.model

        except Exception as e:
            print(f"⚠️ Complexity analysis failed for {chunk.chunk_id}: {e}. Using default model.")
            return self.model

    def enrich_chunk(self, chunk: Chunk) -> Tuple[str, List[str], Dict[str, str], str, Dict[str, List[str]], Dict[str, str], Optional[str], Optional[str], Optional[str], Optional[List[str]]]:
        """
        Generates narrative summary, questions, intents, temporal context, entities, emotions and social dynamics for a chunk.

        Uses complexity-based model routing if enabled.

        Returns:
            (summary, questions, speaker_intents, temporal_context, entities, emotions, interaction_pattern, initiative, emotional_shift, open_loops)
        """
        # Limit text size removed as per user request (128k context available)
        # Using compact content to save tokens (remove timestamps, shorten names)
        content_preview = chunk.get_compact_content()

        prompt = ENRICH_PROMPT.format(
            content=content_preview,
            max_questions=self.config.max_questions
        )

        # Track enrichment timing
        start_time = time.time()
        
        selected_model = self.model
        complexity_score = 0.0
        complexity_category = "unknown"
        metrics_breakdown = None

        try:
            # Select model (outside retry loop to avoid re-analysis)
            if self.provider != "mlx":
                if self.enable_routing:
                    analysis = self.complexity_analyzer.analyze(chunk)
                    complexity_score = analysis.score
                    complexity_category = analysis.category
                    metrics_breakdown = analysis.breakdown
                    selected_model = self._select_model_for_chunk(chunk)
                    self._ensure_model_loaded(selected_model)
                else:
                    selected_model = self.model
            
            # Retry loop
            max_retries = 2
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    if self.provider == "mlx":
                        result = self._call_mlx(prompt)
                    else:
                        result = self._call_ollama(prompt, model=selected_model)

                    # Parse response
                    data = repair_and_load_json(result)
                    parsed_data = parse_enrichment_data(data)
                    
                    # Log success
                    enrichment_time_ms = (time.time() - start_time) * 1000
                    if self.enrichment_logger and self.enable_routing:
                        self.enrichment_logger.log_decision(
                            chunk_id=chunk.chunk_id,
                            complexity_score=complexity_score,
                            complexity_category=complexity_category,
                            selected_model=selected_model,
                            enrichment_time_ms=enrichment_time_ms,
                            message_count=chunk.message_count or 0,
                            participant_count=len(chunk.participants) if chunk.participants else 0,
                            metrics_breakdown=metrics_breakdown
                        )
                    
                    return parsed_data

                except (json.JSONDecodeError, ValueError) as e:
                    last_error = e
                    # Log the malformed content for debugging
                    try:
                        with open("malformed_json_debug.log", "a", encoding="utf-8") as debug_f:
                            debug_f.write(f"--- Chunk {chunk.chunk_id} (Attempt {attempt+1}) ---\n")
                            debug_f.write(f"Error: {e}\n")
                            debug_f.write(f"Content:\n{result}\n")
                            debug_f.write("-" * 50 + "\n")
                    except Exception:
                        pass
                        
                    if attempt < max_retries - 1:
                        print(f"⚠️ JSON error for chunk {chunk.chunk_id} (Attempt {attempt+1}/{max_retries}): {e}. Retrying...")
                        time.sleep(0.5)
                    else:
                        raise e

        except Exception as e:
            enrichment_time_ms = (time.time() - start_time) * 1000
            print(f"⚠️ Enrichment failed for chunk {chunk.chunk_id} after retries: {e}")
            traceback.print_exc()
            
            # Log failure
            if self.enrichment_logger and self.enable_routing:
                self.enrichment_logger.log_decision(
                    chunk_id=chunk.chunk_id,
                    complexity_score=complexity_score,
                    complexity_category=complexity_category,
                    selected_model=selected_model,
                    enrichment_time_ms=enrichment_time_ms,
                    message_count=chunk.message_count or 0,
                    participant_count=len(chunk.participants) if chunk.participants else 0,
                    reason=f"Failed: {str(e)[:50]}"
                )
            
            return "", [], {}, "", {}, {}, None, None, None, None

    def _enrich_chunk_with_model_internal(self, chunk: Chunk, model: str) -> Tuple:
        """Internal method to enrich a chunk with a specific model (skips routing logic)."""
        prompt = ENRICH_PROMPT.format(
            content=chunk.get_compact_content(),
            max_questions=self.config.max_questions
        )
        
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries):
            try:
                if self.provider == "mlx":
                    result = self._call_mlx(prompt)
                else:
                    result = self._call_ollama(prompt, model=model)

                data = repair_and_load_json(result)
                return parse_enrichment_data(data)
            
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                # Log the malformed content for debugging
                try:
                    from .json_utils import clean_llm_json
                    cleaned_debug = clean_llm_json(result)
                    with open("malformed_json_debug.log", "a", encoding="utf-8") as debug_f:
                        debug_f.write(f"--- Chunk {chunk.chunk_id} (Attempt {attempt+1}) [Internal] ---\n")
                        debug_f.write(f"Error: {e}\n")
                        debug_f.write(f"CLEANED Content:\n{cleaned_debug}\n")
                        debug_f.write(f"RAW Content:\n{result}\n")
                        debug_f.write("-" * 50 + "\n")
                except Exception:
                    pass

                if attempt < max_retries - 1:
                    print(f"⚠️ JSON error (internal) for chunk {chunk.chunk_id} (Attempt {attempt+1}/{max_retries}): {e}. Retrying...")
                    time.sleep(0.5)
                else:
                    # Reraise so the caller (batch loop) knows it failed
                    raise e

    def enrich_batch(
        self,
        chunks: List[Chunk],
        progress_callback=None,
        save_callback=None,
        save_interval: int = 20
    ) -> List[Chunk]:
        """
        Enriches a list of chunks with error recovery and OPTIMIZED routing.
        
        Uses a "Batch & Reorder" strategy:
        1. Takes a sub-batch of size `save_interval` (e.g., 20).
        2. Classifies all chunks in the sub-batch.
        3. Processes all 'simple' chunks with the light model.
        4. Processes all 'complex' chunks with the heavy model.
        5. Saves the whole sub-batch sequentially.
        """
        print(f"🔄 Starting batch enrichment (Saving every {save_interval} items)")
        if self.enable_routing:
            print(f"   📊 Complexity routing enabled ({self.loading_strategy} strategy)")
            print(f"   🚀 Optimization: Grouping by model within batches of {save_interval}")

        total = len(chunks)
        
        # Process in sub-batches of size `save_interval`
        for i in range(0, total, save_interval):
            batch_slice = chunks[i : i + save_interval]
            
            # Filter chunks that need processing
            to_process_indices = []
            for local_idx, chunk in enumerate(batch_slice):
                # Skip if already fully enriched
                if chunk.narrative_summary and chunk.hypothetical_questions and chunk.entities:
                    continue
                to_process_indices.append(local_idx)
            
            if not to_process_indices:
                # Nothing to do in this batch, just report progress
                if progress_callback:
                    progress_callback(min(i + save_interval, total), total)
                continue

            # --- OPTIMIZED PROCESSING ---
            if self.enable_routing and self.provider == "ollama":
                # 1. Classification Phase
                simple_indices = []
                complex_indices = []
                analyses = {} # Store analysis to avoid re-computing

                for local_idx in to_process_indices:
                    chunk = batch_slice[local_idx]
                    try:
                        analysis = self.complexity_analyzer.analyze(chunk)
                        analyses[local_idx] = analysis
                        
                        # Decide category
                        category = analysis.category
                        use_light = True
                        if category == "complex":
                            use_light = False
                        elif category == "medium":
                            # Check config for medium routing
                            use_light = getattr(self.config, 'complexity_medium_uses_light', True)
                        
                        if use_light:
                            simple_indices.append(local_idx)
                        else:
                            complex_indices.append(local_idx)
                            
                    except Exception as e:
                        print(f"⚠️ Analysis failed for batch item {local_idx}: {e}")
                        analyses[local_idx] = None
                        complex_indices.append(local_idx) # Fallback to strong model
                
                # 2. Execution Phase - Group by Model
                # Strategy: Execute the group that matches current model first to minimize swaps
                groups = [
                    (simple_indices, self.light_model, "simple"),
                    (complex_indices, self.model, "complex or medium")
                ]
                
                # If strong model is currently loaded, do complex first
                if self.current_loaded_model == self.model:
                     groups.reverse()
                
                for indices, model_name, label in groups:
                    if not indices:
                        continue
                        
                    # Load model once for the group
                    self._ensure_model_loaded(model_name)
                    
                    for local_idx in indices:
                        chunk = batch_slice[local_idx]
                        analysis = analyses.get(local_idx)
                        
                        start_time = time.time()
                        try:
                            # Use internal method to skip redundant routing logic
                            res = self._enrich_chunk_with_model_internal(chunk, model_name)
                            
                            # Update chunk references
                            (chunk.narrative_summary, chunk.hypothetical_questions, 
                             chunk.speaker_intents, chunk.temporal_context, 
                             chunk.entities, chunk.emotions, 
                             chunk.interaction_pattern, chunk.initiative, 
                             chunk.emotional_shift, chunk.open_loops) = res
                            
                            # Logging
                            enrichment_time_ms = (time.time() - start_time) * 1000
                            
                            # Update stats
                            if label == "simple": self.routing_stats["simple"] += 1
                            elif label == "complex": self.routing_stats["complex"] += 1
                            else: self.routing_stats["medium"] += 1 # Approximation
                            
                            if self.enrichment_logger:
                                self.enrichment_logger.log_decision(
                                    chunk_id=chunk.chunk_id,
                                    complexity_score=analysis.score if analysis else 0.0,
                                    complexity_category=analysis.category if analysis else "unknown",
                                    selected_model=model_name,
                                    enrichment_time_ms=enrichment_time_ms,
                                    message_count=chunk.message_count or 0,
                                    participant_count=len(chunk.participants) if chunk.participants else 0,
                                    metrics_breakdown=analysis.breakdown if analysis else None
                                )
                                
                        except Exception as e:
                            print(f"⚠️ Error enriching chunk {chunk.chunk_id}: {e}")
                            traceback.print_exc()
                            # Log failure ...

            else:
                # Standard linear processing (No routing or MLX)
                for local_idx in to_process_indices:
                    chunk = batch_slice[local_idx]
                    # Logic reuse from enrich_chunk call...
                    # For simplicity, we just call the existing enrich_chunk which handles everything
                    # ensuring we manually assign fields back if not done in place (enrich_chunk usually returns tuple)
                    try:
                        res = self.enrich_chunk(chunk)
                        (chunk.narrative_summary, chunk.hypothetical_questions, 
                         chunk.speaker_intents, chunk.temporal_context, 
                         chunk.entities, chunk.emotions, 
                         chunk.interaction_pattern, chunk.initiative, 
                         chunk.emotional_shift, chunk.open_loops) = res
                    except Exception as e:
                        print(f"⚠️ Error in standard enrichment: {e}")
                        traceback.print_exc()

            # Update progress
            if progress_callback:
                progress_callback(min(i + save_interval, total), total)

            # SAVE (The integrity checkpoint)
            if save_callback:
                try:
                    # We save the WHOLE list, but only the current batch has changed
                    # This relies on the fact that `chunks` are updated in-place
                    save_callback()
                    print(f"   💾 Saved batch {i // save_interval + 1} (up to item {min(i + save_interval, total)})")
                    if self.enrichment_logger:
                        self.enrichment_logger.save()
                except Exception as e:
                    print(f"⚠️ Save failed: {e}")

        # Final stats
        if self.enrichment_logger:
            self.enrichment_logger.save()
            self.enrichment_logger.export_csv()
            self.enrichment_logger.print_summary()

        if self.enable_routing and sum(self.routing_stats.values()) > 0:
            self._print_routing_stats()

        return chunks

    def _print_routing_stats(self):
        """Print routing statistics summary."""
        total = (self.routing_stats["simple"] +
                 self.routing_stats["medium"] +
                 self.routing_stats["complex"])

        if total == 0:
            return

        print("\n" + "="*60)
        print("📊 COMPLEXITY ROUTING STATISTICS")
        print("="*60)
        print(f"Simple chunks:   {self.routing_stats['simple']:6} ({100*self.routing_stats['simple']/total:.1f}%)")
        print(f"Medium chunks:   {self.routing_stats['medium']:6} ({100*self.routing_stats['medium']/total:.1f}%)")
        print(f"Complex chunks:  {self.routing_stats['complex']:6} ({100*self.routing_stats['complex']/total:.1f}%)")
        print(f"{'─'*60}")
        print(f"Model switches:  {self.routing_stats['model_switches']}")
        if self.routing_stats['model_switches'] > 0:
            avg_switch_time = self.routing_stats['total_switch_time_ms'] / self.routing_stats['model_switches']
            print(f"Avg switch time: {avg_switch_time:.0f}ms")
        print("="*60 + "\n")