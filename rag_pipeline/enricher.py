"""
Chunk enricher using an LLM to generate narrative summaries
and hypothetical questions (advanced RAG techniques).

Supports complexity-based model routing: simple chunks → 3B model,
complex chunks → 8B model for faster indexing with acceptable quality.
"""
import json
import time
import traceback
from typing import List, Optional, Tuple, Dict

from .config import Config, default_config
from .chunker import Chunk
from .complexity_analyzer import ChunkComplexityAnalyzer
from .enrichment_log import EnrichmentLogger
from .json_utils import repair_and_load_json, parse_enrichment_data, clean_llm_json
from .prompts import ENRICH_PROMPT
from .enrichment_validator import is_corrupted_output, is_low_quality_enrichment
from .model_manager import EnrichmentModelManager
from .enrichment_batcher import EnrichmentBatcher

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

        # Model Management
        self.model_manager = EnrichmentModelManager(self.config, provider=self.provider)
        self.model = self.model_manager.model
        self.light_model = self.model_manager.light_model

        # MLX setup (specific to this class for now as it holds state)
        self.mlx_provider = None
        if self.provider == "mlx":
            from .mlx_provider import MlxProvider
            mlx_model = "mlx-community/Ministral-3-8B-Instruct-2512-4bit"
            if "/" in self.model:
                mlx_model = self.model
            print(f"[Enricher] Loading MLX model: {mlx_model}")
            self.mlx_provider = MlxProvider(model_path=mlx_model)

        # Complexity-based routing setup
        self.enable_routing = getattr(self.config, 'enable_complexity_routing', True)
        self.force_model = getattr(self.config, 'force_model', None)
        self.complexity_analyzer = ChunkComplexityAnalyzer(self.config) if self.enable_routing else None

        # Enrichment logging
        self.enrichment_logger = EnrichmentLogger() if self.enable_routing else None

        if self.provider == "ollama" and self.enable_routing:
            if getattr(self.config, 'model_loading_strategy', 'dual') == "dual":
                self.model_manager.preload_models()

    def _call_mlx(self, prompt: str) -> str:
        """Call MLX provider."""
        if not self.mlx_provider:
             raise ValueError("MLX provider not initialized")
        messages = [{"role": "user", "content": prompt}]
        return self.mlx_provider.generate_chat(messages, temperature=0.1)

    def _select_model_for_chunk(self, chunk: Chunk) -> str:
        """Select which model to use for a chunk based on complexity."""
        if self.force_model:
            return self.force_model
        if not self.enable_routing:
            return self.model

        try:
            analysis = self.complexity_analyzer.analyze(chunk)
            if analysis.category == "simple":
                self.model_manager.update_stats("simple")
                return self.light_model
            elif analysis.category == "medium":
                self.model_manager.update_stats("medium")
                use_light = getattr(self.config, 'complexity_medium_uses_light', True)
                return self.light_model if use_light else self.model
            else:  # complex
                self.model_manager.update_stats("complex")
                return self.model
        except Exception as e:
            print(f"⚠️ Complexity analysis failed for {chunk.chunk_id}: {e}. Using default model.")
            return self.model

    def enrich_chunk(self, chunk: Chunk) -> Tuple:
        """
        Generates narrative summary, questions, intents, etc. for a chunk.
        """
        content_preview = chunk.get_compact_content()
        prompt = ENRICH_PROMPT.format(
            content=content_preview,
            max_questions=self.config.max_questions
        )

        start_time = time.time()
        selected_model = self.model
        complexity_score = 0.0
        complexity_category = "unknown"
        metrics_breakdown = None

        try:
            if self.provider != "mlx":
                if self.enable_routing:
                    analysis = self.complexity_analyzer.analyze(chunk)
                    complexity_score = analysis.score
                    complexity_category = analysis.category
                    metrics_breakdown = analysis.breakdown
                    selected_model = self._select_model_for_chunk(chunk)
                    self.model_manager.ensure_model_loaded(selected_model)
                else:
                    selected_model = self.model
            
            # Retry loop
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    if self.provider == "mlx":
                        result = self._call_mlx(prompt)
                    else:
                        result = self.model_manager.call_ollama(prompt, model=selected_model)

                    data = repair_and_load_json(result)
                    parsed_data = parse_enrichment_data(data)
                    
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
                    from .json_utils import log_malformed_json
                    log_malformed_json(result if 'result' in locals() else "", e, chunk.chunk_id, attempt+1, selected_model)
                    
                    if attempt < max_retries - 1:
                        print(f"⚠️ JSON error for chunk {chunk.chunk_id} (Attempt {attempt+1}/{max_retries}): {e}. Retrying...")
                        time.sleep(0.5)
                    else:
                        raise e

        except Exception as e:
            enrichment_time_ms = (time.time() - start_time) * 1000
            print(f"⚠️ Enrichment failed for chunk {chunk.chunk_id} after retries: {e}")
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
        """Internal method to enrich a chunk with a specific model."""
        prompt = ENRICH_PROMPT.format(
            content=chunk.get_compact_content(),
            max_questions=self.config.max_questions
        )
        
        max_retries = 2
        current_model = model
        
        for attempt in range(max_retries):
            try:
                if self.provider == "mlx":
                    result = self._call_mlx(prompt)
                else:
                    result = self.model_manager.call_ollama(prompt, model=current_model)

                if is_corrupted_output(result):
                    if current_model == self.light_model and self.provider != "mlx":
                        print(f"⚠️ Corruption detected for {chunk.chunk_id}, retrying with {self.model}...")
                        current_model = self.model
                        result = self.model_manager.call_ollama(prompt, model=current_model)
                        if is_corrupted_output(result):
                            raise ValueError(f"Corrupted output even with {self.model}")
                    else:
                        raise ValueError("Corrupted output detected")

                data = repair_and_load_json(result)
                enrichment_data = parse_enrichment_data(data)
                
                if current_model == self.light_model and self.provider != "mlx":
                    if is_low_quality_enrichment(enrichment_data):
                        print(f"⚠️ Low-quality output for {chunk.chunk_id}, retrying with {self.model}...")
                        current_model = self.model
                        result = self.model_manager.call_ollama(prompt, model=current_model)
                        data = repair_and_load_json(result)
                        enrichment_data = parse_enrichment_data(data)
                
                return enrichment_data
            
            except (json.JSONDecodeError, ValueError) as e:
                from .json_utils import log_malformed_json
                log_malformed_json(result if 'result' in locals() else "", e, chunk.chunk_id, attempt+1, current_model)
                
                if attempt < max_retries - 1:
                    print(f"⚠️ JSON error for chunk {chunk.chunk_id} (Attempt {attempt+1}/{max_retries}): {e}. Retrying...")
                    time.sleep(0.5)
                else:
                    raise e

    def enrich_batch(
        self,
        chunks: List[Chunk],
        progress_callback=None,
        save_callback=None,
        save_interval: int = 20
    ) -> List[Chunk]:
        """Enriches chunks using the EnrichmentBatcher."""
        batcher = EnrichmentBatcher(
            enricher=self,
            save_interval=save_interval,
            progress_callback=progress_callback,
            save_callback=save_callback
        )
        
        results = batcher.process(chunks)

        # Final stats
        if self.enrichment_logger:
            self.enrichment_logger.save()
            self.enrichment_logger.export_csv()
            self.enrichment_logger.print_summary()

        if self.enable_routing:
            self.model_manager.print_routing_stats()

        return results
