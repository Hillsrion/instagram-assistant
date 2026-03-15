"""
Hierarchical summary generator via LLM.
Generates ConversationSummary and PeriodSummary from enriched chunks.
"""
import json
import requests
import time
import re
import psutil
import traceback
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from rag_pipeline.core.config import Config, default_config
from rag_pipeline.core.models import Chunk
from rag_pipeline.summaries.summary_models import ConversationSummary, PeriodSummary
from rag_pipeline.core.prompts import CONVERSATION_SUMMARY_PROMPT, PERIOD_SUMMARY_PROMPT
from rag_pipeline.enrichment.json_utils import repair_and_load_json, parse_summary_data
from rag_pipeline.core.schemas import CONVERSATION_SUMMARY_SCHEMA, PERIOD_SUMMARY_SCHEMA


class SummaryGenerator:
    """Generates hierarchical summaries from chunks with dual-model strategy."""

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.model = self.config.llm_model
        self.light_model = getattr(self.config, 'llm_light_model', 'ministral-3:3b')
        self.enable_routing = getattr(self.config, 'enable_complexity_routing', True)
        self.current_loaded_model = None
        
        # Preload models if using dual strategy
        if self.enable_routing:
            self._preload_models()

    def _preload_models(self):
        """Preload both light and strong models."""
        try:
            available_ram_gb = psutil.virtual_memory().available / (1024 ** 3)
            min_required = getattr(self.config, 'min_ram_gb_for_dual', 10.0)

            if available_ram_gb < min_required:
                return

            print(f"🔄 Preloading models for Summarizer...")
            for model_name in [self.light_model, self.model]:
                try:
                    self._call_ollama("test", model=model_name)
                except:
                    pass
            self.current_loaded_model = self.model
        except Exception as e:
            print(f"⚠️ Failed to preload models for Summarizer: {e}")

    def _ensure_model_loaded(self, model_name: str):
        """Ensure specific model is loaded."""
        if self.current_loaded_model != model_name:
            try:
                self._call_ollama("test", model=model_name)
                self.current_loaded_model = model_name
            except Exception as e:
                print(f"⚠️ Failed to load {model_name}: {e}")

    def _call_ollama(self, prompt: str, model: str, response_format: Optional[str] = None) -> str:
        """Call Ollama chat API, using multi-endpoint if configured."""
        # Use multi-endpoint provider if load balancing is enabled
        use_lb = getattr(self.config, 'use_load_balancing', False)
        endpoints = getattr(self.config, 'ollama_endpoints', [self.config.ollama_url])
        if use_lb and len(endpoints) > 1:
            # Use MultiOllamaProvider for load balancing
            if not hasattr(self, '_multi_provider') or self._multi_provider is None:
                from rag_pipeline.core.multi_ollama_provider import MultiOllamaProvider
                self._multi_provider = MultiOllamaProvider(self.config, model, endpoints)
            elif self._multi_provider.model != model:
                self._multi_provider.model = model
            
            messages = [{"role": "user", "content": prompt}]
            return self._multi_provider.generate(
                messages,
                temperature=0.0,
                num_ctx=self.config.num_ctx,
                max_tokens=1024,
                format=response_format
            )
        else:
            # Single endpoint - use direct request
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {
                    "temperature": 0.0,  # Deterministic for JSON
                    "num_ctx": self.config.num_ctx,
                    "num_predict": 1024,
                }
            }
            
            if response_format == "json":
                payload["format"] = "json"

            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                timeout=180
            )
            response.raise_for_status()
            return response.json()["message"]["content"]

    def _is_corrupted_output(self, raw: str) -> bool:
        """Detect corrupted LLM outputs (repetition loops, truncation)."""
        if not raw: return True
        if re.search(r'(.)\1{10,}', raw): return True
        
        stripped = raw.strip()
        if '```' in stripped:
            parts = stripped.split('```')
            if len(parts) >= 2:
                stripped = parts[1].replace('json', '').strip()
        
        return len(stripped) < 40

    def _is_low_quality_summary(self, data: dict, summary_type: str) -> bool:
        """Detect low-quality summaries (empty fields)."""
        summary = data.get("summary", "")
        if not summary or len(summary) < 50:
            return True
            
        if summary_type == "conversation":
            if not data.get("main_topics") or len(data.get("main_topics")) < 2:
                return True
        else: # period
            if not data.get("topics") or len(data.get("topics")) < 1:
                return True
                
        return False

    def _select_model(self, chunks: List[Chunk]) -> str:
        """Heuristic model selection for summaries."""
        if not self.enable_routing:
            return self.model
            
        # If processing more than 15 chunks or 200 messages, use strong model
        total_messages = sum(c.message_count for c in chunks)
        if len(chunks) > 15 or total_messages > 200:
            return self.model
            
        return self.light_model

    def _call_llm_with_strategy(self, prompt: str, chunks: List[Chunk], summary_type: str) -> Optional[dict]:
        """Calls LLM with dual-model strategy and JSON repairs."""
        selected_model = self._select_model(chunks)
        current_model = selected_model
        
        max_retries = 2
        used_fallback = False
        
        # Identify the context for logging
        context_id = f"{summary_type}_{chunks[0].conversation_id}" if chunks else "unknown"
        
        for attempt in range(max_retries):
            result = None
            try:
                self._ensure_model_loaded(current_model)
                schema = CONVERSATION_SUMMARY_SCHEMA if summary_type == "conversation" else PERIOD_SUMMARY_SCHEMA
                result = self._call_ollama(prompt, model=current_model, response_format=schema)

                # 1. Corruption Check (Repetition loops, truncation)
                if self._is_corrupted_output(result):
                    if current_model == self.light_model:
                        print(f"⚠️ Corruption in summary ({current_model}), falling back to {self.model}...")
                        current_model = self.model
                        used_fallback = True
                        schema = CONVERSATION_SUMMARY_SCHEMA if summary_type == "conversation" else PERIOD_SUMMARY_SCHEMA
                        result = self._call_ollama(prompt, model=current_model, response_format=schema)
                        if self._is_corrupted_output(result):
                            raise ValueError("Corrupted output even with strong model")
                    else:
                        raise ValueError("Corrupted output detected (repetition or truncation)")

                # 2. JSON Repair & Parse
                data = repair_and_load_json(result)
                parsed = parse_summary_data(data, summary_type)
                
                # 3. Quality Check (Sparse fields)
                if current_model == self.light_model:
                    if self._is_low_quality_summary(parsed, summary_type):
                        print(f"⚠️ Low-quality summary ({current_model}), retrying with {self.model}...")
                        current_model = self.model
                        used_fallback = True
                        schema = CONVERSATION_SUMMARY_SCHEMA if summary_type == "conversation" else PERIOD_SUMMARY_SCHEMA
                        result = self._call_ollama(prompt, model=current_model, response_format=schema)
                        data = repair_and_load_json(result)
                        parsed = parse_summary_data(data, summary_type)
                
                return parsed

            except Exception as e:
                # Log the malformed content for debugging (same as Enricher)
                try:
                    from rag_pipeline.core.logger import LOG_DIR
                    from rag_pipeline.enrichment.json_utils import clean_llm_json
                    debug_log_path = LOG_DIR / "malformed_summary_json_debug.log"
                    with open(debug_log_path, "a", encoding="utf-8") as debug_f:
                        debug_f.write(f"--- {context_id} (Attempt {attempt+1}) [Model: {current_model}] ---\n")
                        debug_f.write(f"Error: {e}\n")
                        debug_f.write(f"Fallback used: {used_fallback}\n")
                        if result:
                            try:
                                cleaned_debug = clean_llm_json(result)
                                debug_f.write(f"CLEANED Content:\n{cleaned_debug}\n")
                            except:
                                pass
                            debug_f.write(f"RAW Content:\n{result}\n")
                        else:
                            debug_f.write("RAW Content: (No result)\n")
                        debug_f.write("-" * 50 + "\n")
                except Exception:
                    pass

                print(f"⚠️ Summary error for {context_id} (Attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    # On last attempt, force strong model if not already using it
                    if not used_fallback:
                        current_model = self.model
                        used_fallback = True
                else:
                    return None

    def _group_chunks_by_conversation(self, chunks: List[Chunk]) -> Dict[str, List[Chunk]]:
        """Groups chunks by conversation_id."""
        grouped = defaultdict(list)
        for chunk in chunks:
            grouped[chunk.conversation_id].append(chunk)

        # Sort by date within each conversation
        for conv_id in grouped:
            grouped[conv_id].sort(key=lambda c: c.date_start)

        return dict(grouped)

    def _group_chunks_by_period(self, chunks: List[Chunk]) -> Dict[str, List[Chunk]]:
        """Groups chunks by month (YYYY-MM)."""
        grouped = defaultdict(list)
        for chunk in chunks:
            period = chunk.date_start[:7]  # "YYYY-MM"
            grouped[period].append(chunk)

        return dict(grouped)

    def generate_conversation_summary(
        self,
        conversation_id: str,
        chunks: List[Chunk]
    ) -> Optional[ConversationSummary]:
        """Generates a global summary for a conversation."""
        if not chunks:
            return None

        # Collect narrative_summary from each chunk
        summaries = []
        for chunk in chunks:
            if chunk.narrative_summary:
                date_str = chunk.date_start[:10]
                summaries.append(f"[{date_str}] {chunk.narrative_summary}")

        participants = chunks[0].participants if chunks else []
        participants_str = ", ".join(participants)

        # Limit number of summaries to avoid exceeding context window
        max_summaries = 60
        if len(summaries) > max_summaries:
            step = len(summaries) // max_summaries
            summaries = summaries[::step][:max_summaries]

        prompt = CONVERSATION_SUMMARY_PROMPT.format(
            participants=participants_str,
            narrative_summaries="\n".join(summaries)
        )

        result = self._call_llm_with_strategy(prompt, chunks, "conversation")
        if not result:
            return None

        total_messages = sum(c.message_count for c in chunks)
        date_start = min(c.date_start for c in chunks)
        date_end = max(c.date_end for c in chunks)
        chunk_ids = [c.chunk_id for c in chunks]

        return ConversationSummary(
            summary_id=f"{conversation_id}_summary",
            conversation_id=conversation_id,
            participants=participants,
            date_start=date_start,
            date_end=date_end,
            total_messages=total_messages,
            total_chunks=len(chunks),
            summary=result.get("summary", ""),
            main_topics=result.get("main_topics", []),
            relationship_dynamic=result.get("relationship_dynamic", ""),
            notable_events=result.get("notable_events", []),
            chunk_ids=chunk_ids
        )

    def generate_period_summary(
        self,
        conversation_id: str,
        period: str,
        chunks: List[Chunk]
    ) -> Optional[PeriodSummary]:
        """Generates a summary for a period (month) of a conversation."""
        if not chunks:
            return None

        summaries = []
        for chunk in chunks:
            if chunk.narrative_summary:
                date_str = chunk.date_start[:10]
                summaries.append(f"[{date_str}] {chunk.narrative_summary}")

        participants = chunks[0].participants if chunks else []
        participants_str = ", ".join(participants)

        try:
            period_date = datetime.strptime(period, "%Y-%m")
            period_display = period_date.strftime("%B %Y")
        except ValueError:
            period_display = period

        prompt = PERIOD_SUMMARY_PROMPT.format(
            participants=participants_str,
            period=period_display,
            narrative_summaries="\n".join(summaries)
        )

        result = self._call_llm_with_strategy(prompt, chunks, "period")
        if not result:
            return None

        message_count = sum(c.message_count for c in chunks)
        date_start = min(c.date_start for c in chunks)
        date_end = max(c.date_end for c in chunks)
        chunk_ids = [c.chunk_id for c in chunks]

        return PeriodSummary(
            summary_id=f"{conversation_id}_period_{period}",
            conversation_id=conversation_id,
            participants=participants,
            period=period,
            date_start=date_start,
            date_end=date_end,
            message_count=message_count,
            summary=result.get("summary", ""),
            topics=result.get("topics", []),
            mood=result.get("mood", ""),
            chunk_ids=chunk_ids
        )

    def generate_period_summaries(
        self,
        conversation_id: str,
        chunks: List[Chunk],
        progress_callback=None
    ) -> List[PeriodSummary]:
        """Generates monthly summaries for a conversation."""
        chunks_by_period = self._group_chunks_by_period(chunks)

        summaries = []
        periods = sorted(chunks_by_period.keys())

        for i, period in enumerate(periods):
            period_chunks = chunks_by_period[period]
            summary = self.generate_period_summary(conversation_id, period, period_chunks)
            if summary:
                summaries.append(summary)

            if progress_callback:
                progress_callback(i + 1, len(periods))

        return summaries

    def generate_all_summaries(
        self,
        chunks: List[Chunk],
        progress_callback=None,
        save_callback=None
    ) -> Tuple[List[ConversationSummary], List[PeriodSummary]]:
        """Generates all summaries for all chunks."""
        chunks_by_conversation = self._group_chunks_by_conversation(chunks)

        conversation_summaries = []
        period_summaries = []

        conversations = list(chunks_by_conversation.keys())
        total_steps = len(conversations) * 2
        current_step = 0

        for conv_id in conversations:
            conv_chunks = chunks_by_conversation[conv_id]

            # 1. Conversation summary
            conv_summary = self.generate_conversation_summary(conv_id, conv_chunks)
            if conv_summary:
                conversation_summaries.append(conv_summary)

            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps, f"Conv: {conv_id[:30]}")

            # 2. Period summaries
            period_sums = self.generate_period_summaries(conv_id, conv_chunks)
            period_summaries.extend(period_sums)

            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps, f"Periods: {conv_id[:30]}")

            if save_callback:
                save_callback(conversation_summaries, period_summaries)

        return conversation_summaries, period_summaries