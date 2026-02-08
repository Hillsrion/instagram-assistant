"""
Batch processing logic for chunk enrichment.
Implements the "Batch & Reorder" strategy to minimize model switching.
"""
import time
import traceback
from typing import List, Callable, Optional
from rag_pipeline.core.models import Chunk

class EnrichmentBatcher:
    """Handles batch enrichment with optimized model routing."""

    def __init__(
        self, 
        enricher, 
        save_interval: int = 20,
        progress_callback: Optional[Callable] = None,
        save_callback: Optional[Callable] = None
    ):
        self.enricher = enricher
        self.save_interval = save_interval
        self.progress_callback = progress_callback
        self.save_callback = save_callback

    def process(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Enriches a list of chunks with error recovery and OPTIMIZED routing.
        """
        print(f"🔄 Starting batch enrichment (Saving every {self.save_interval} items)")
        if self.enricher.enable_routing:
            print(f"   📊 Complexity routing enabled ({self.enricher.model_manager.loading_strategy} strategy)")
            print(f"   🚀 Optimization: Grouping by model within batches of {self.save_interval}")

        total = len(chunks)
        
        for i in range(0, total, self.save_interval):
            batch_slice = chunks[i : i + self.save_interval]
            
            # Filter chunks that need processing
            to_process_indices = []
            for local_idx, chunk in enumerate(batch_slice):
                if chunk.enrichment_failed:
                    continue
                if chunk.narrative_summary and chunk.hypothetical_questions and chunk.entities:
                    continue
                to_process_indices.append(local_idx)
            
            if not to_process_indices:
                if self.progress_callback:
                    self.progress_callback(min(i + self.save_interval, total), total)
                continue

            # --- OPTIMIZED PROCESSING ---
            if self.enricher.enable_routing and self.enricher.provider == "ollama":
                # 1. Classification Phase
                simple_indices = []
                complex_indices = []
                analyses = {}

                for local_idx in to_process_indices:
                    chunk = batch_slice[local_idx]
                    try:
                        analysis = self.enricher.complexity_analyzer.analyze(chunk)
                        analyses[local_idx] = analysis
                        
                        category = analysis.category
                        use_light = True
                        if category == "complex":
                            use_light = False
                        elif category == "medium":
                            use_light = getattr(self.enricher.config, 'complexity_medium_uses_light', True)
                        
                        if use_light:
                            simple_indices.append(local_idx)
                        else:
                            complex_indices.append(local_idx)
                    except Exception as e:
                        print(f"⚠️ Analysis failed for batch item {local_idx}: {e}")
                        analyses[local_idx] = None
                        complex_indices.append(local_idx)
                
                # 2. Execution Phase - Group by Model
                groups = [
                    (simple_indices, self.enricher.model_manager.light_model, "simple"),
                    (complex_indices, self.enricher.model_manager.model, "complex or medium")
                ]
                
                # Sort groups to minimize swaps
                if self.enricher.model_manager.current_loaded_model == self.enricher.model_manager.model:
                     groups.reverse()
                
                for indices, model_name, label in groups:
                    if not indices:
                        continue
                        
                    self.enricher.model_manager.ensure_model_loaded(model_name)
                    
                    for local_idx in indices:
                        chunk = batch_slice[local_idx]
                        analysis = analyses.get(local_idx)
                        
                        start_time = time.time()
                        try:
                            res = self.enricher._enrich_chunk_with_model_internal(chunk, model_name)
                            
                            (chunk.narrative_summary, chunk.hypothetical_questions, 
                             chunk.speaker_intents, chunk.temporal_context, 
                             chunk.entities, chunk.emotions, 
                             chunk.interaction_pattern, chunk.initiative, 
                             chunk.emotional_shift, chunk.open_loops) = res
                            
                            enrichment_time_ms = (time.time() - start_time) * 1000
                            
                            # Update stats
                            if label == "simple": self.enricher.model_manager.update_stats("simple")
                            elif label == "complex": self.enricher.model_manager.update_stats("complex")
                            else: self.enricher.model_manager.update_stats("medium")
                            
                            if self.enricher.enrichment_logger:
                                self.enricher.enrichment_logger.log_decision(
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
                            chunk.enrichment_failed = True
                            chunk.enrichment_error = str(e)
            else:
                # Standard linear processing
                for local_idx in to_process_indices:
                    chunk = batch_slice[local_idx]
                    try:
                        res = self.enricher.enrich_chunk(chunk)
                        (chunk.narrative_summary, chunk.hypothetical_questions, 
                         chunk.speaker_intents, chunk.temporal_context, 
                         chunk.entities, chunk.emotions, 
                         chunk.interaction_pattern, chunk.initiative, 
                         chunk.emotional_shift, chunk.open_loops) = res
                    except Exception as e:
                        print(f"⚠️ Error in standard enrichment for {chunk.chunk_id}: {e}")
                        traceback.print_exc()
                        chunk.enrichment_failed = True
                        chunk.enrichment_error = str(e)

            if self.progress_callback:
                self.progress_callback(min(i + self.save_interval, total), total)

            if self.save_callback:
                try:
                    self.save_callback()
                    print(f"   💾 Saved batch {i // self.save_interval + 1} (up to item {min(i + self.save_interval, total)})")
                    if self.enricher.enrichment_logger:
                        self.enricher.enrichment_logger.save()
                except Exception as e:
                    print(f"⚠️ Save failed: {e}")

        return chunks
