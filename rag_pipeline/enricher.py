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
from typing import List, Optional, Tuple, Dict
from .config import Config, default_config
from .chunker import Chunk
from .complexity_analyzer import ChunkComplexityAnalyzer
from .enrichment_log import EnrichmentLogger

# Prompt kept in French as it processes French data
ENRICH_PROMPT = """Tu es un analyseur de conversations (STRICT, basé sur le texte uniquement).

ANALYSE CETTE CONVERSATION ET GÉNÈRE JSON :

1. **RÉSUMÉ** : 1 phrase max, l'action/intention/résultat
2. **QUESTIONS** : 1 à {max_questions} questions précises que cet extrait répond (inclure des questions sur la dynamique sociale si pertinent : qui mène, changement d'humeur, etc.)
3. **INTENTIONS** : Pour chaque participant → son objectif principal (une phrase max)
4. **CONTEXTE TEMPOREL** : Moment/période (ex: "avant X", "durant vacances")
5. **ENTITÉS** : Éléments EXPLICITEMENT mentionnés dans le texte :
   - locations : villes, lieux, restaurants cités dans les messages
   - people : personnes mentionnées (hors participants directs)
   - media : films, séries, jeux, musiques cités
   - events : événements, fêtes, réunions cités
   - Si une catégorie n'a AUCUNE mention dans le texte → liste vide []
   - N'invente RIEN. Ne remplis PAS un champ juste pour le remplir.
6. **ÉMOTIONS** : Ambiance générale de l'échange:
   - dominant: émotion principale (basée sur le texte)
   - tone: ton général (léger, sérieux, playful, etc)
   - tension_level: low/medium/high
7. **DYNAMIQUE SOCIALE** :
   - interaction_pattern: Type d'échange dominant (ex: "Planification", "Récit", "Débat", "Soutien", "Conflit", "Catch-up"). Si aucun pattern clair n'est identifiable ou si l'échange est trop fragmenté, mets null.
   - initiative: Qui mène ? (ex: "Nom_A", "Équilibré", "Nom_B pose les questions")
   - emotional_shift: Trajectoire (ex: "Neutre -> Joyeux", "Tendu -> Apaisé", "Stable")
   - open_loops: Sujets lancés mais non résolus (liste de strings, vide si aucun)

CONVERSATION:
{content}

RÈGLES STRICTES:
- Format JSON obligatoire, ZÉRO texte avant ou après
- ZÉRO détails non présents dans le texte
- Si un champ entités n'a pas de correspondance dans le texte → [] (liste vide)
- Ne recopie JAMAIS les exemples ci-dessous, ils illustrent uniquement le format

FORMAT JSON (les valeurs sont des exemples de format, PAS des données à recopier):
{{
  "narrative_summary": "<1 phrase décrivant l'échange>",
  "questions": ["<question 1>", "<éventuelle question 2>", "..."],
  "speaker_intents": {{
    "<participant>": "<son intention>"
  }},
  "temporal_context": "<moment ou période>",
  "entities": {{ "locations": [], "people": [], "media": [], "events": [] }},
  "emotions": {{ "dominant": "<émotion>", "tone": "<ton>", "tension_level": "low|medium|high" }},
  "interaction_pattern": "<type d'échange>",
  "initiative": "<qui mène>",
  "emotional_shift": "<trajectoire>",
  "open_loops": []
}}
"""

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

    def _clean_json(self, json_str: str) -> str:
        """Cleans JSON string from common LLM artifacts and fixes unescaped quotes."""
        cleaned = json_str.strip()
        # Remove markdown code blocks
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        
        if "```" in cleaned:
            cleaned = cleaned.split("```")[0]
            
        cleaned = cleaned.strip()
        
        # If it doesn't start with {, try to find it
        if not cleaned.startswith("{") and "{" in cleaned:
            cleaned = cleaned[cleaned.find("{"):]
            
        # Fix trailing commas before closing symbols
        cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
        
        # Robust fix for unescaped quotes inside string values
        lines = cleaned.split('\n')
        fixed_lines = []
        
        for line in lines:
            stripped_line = line.strip()
            
            # Case 1: "key": "value"
            if ':' in line and '"' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key_part = parts[0]
                    val_part = parts[1].strip()
                    if val_part.startswith('"') and (val_part.endswith(',') or val_part.endswith('"')):
                        has_comma = val_part.endswith(',')
                        content = val_part[1:-2] if has_comma else val_part[1:-1]
                        if '"' in content:
                            content = content.replace('"', '\\"')
                            val_part = f'"{content}"'
                            if has_comma: val_part += ','
                            line = f"{key_part}: {val_part}"
            
            # Case 2: List item: "value" or "value",
            elif stripped_line.startswith('"') and (stripped_line.endswith('"') or stripped_line.endswith('",')):
                has_comma = stripped_line.endswith(',')
                content_part = stripped_line[1:-2] if has_comma else stripped_line[1:-1]
                if '"' in content_part:
                    fixed_content = content_part.replace('"', '\\"')
                    indent = line[:line.find('"')]
                    line = f'{indent}"{fixed_content}"'
                    if has_comma: line += ","
            
            fixed_lines.append(line)
        
        # Second pass: Fix missing commas between fields
        final_lines = []
        for i, line in enumerate(fixed_lines):
            line = line.rstrip()
            next_line = None
            for j in range(i + 1, len(fixed_lines)):
                if fixed_lines[j].strip():
                    next_line = fixed_lines[j].strip()
                    break
            if next_line:
                stripped = line.strip()
                if stripped.endswith('"') or stripped.endswith(']') or stripped.endswith('}'):
                    if next_line.startswith('"') or next_line.startswith('{') or next_line.startswith('['):
                         line += ","
            final_lines.append(line)
            
        return '\n'.join(final_lines)

    def _parse_enrichment_response(self, result: str) -> Tuple:
        """Parses the LLM response into enrichment fields."""
        if not result:
            raise ValueError("Empty response from LLM")
            
        cleaned_result = self._clean_json(result)
        
        try:
            data = json.loads(cleaned_result)
            return self._parse_enrichment_data(data)

        except json.JSONDecodeError as e:
            # Fallback: if it's truncated, try to close the JSON manually
            if "{" in cleaned_result and not cleaned_result.endswith("}"):
                try:
                    # Very simple recovery for partial objects
                    recovered = cleaned_result
                    if recovered.count("{") > recovered.count("}"):
                         recovered += "}" * (recovered.count("{") - recovered.count("}") )
                    data = json.loads(recovered)
                    return self._parse_enrichment_data(data)
                except:
                    raise e
            else:
                raise e

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
                    parsed_data = self._parse_enrichment_response(result)
                    
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

    def _parse_enrichment_data(self, data: dict) -> Tuple:
        """Robustly parse the JSON data returned by the LLM."""
        
        # Helper to ensure string lists
        def ensure_str_list(lst):
            if isinstance(lst, list):
                return [str(x) if not isinstance(x, str) else x for x in lst]
            if isinstance(lst, str) and lst.strip():
                return [lst.strip()]
            return []

        # Helper to ensure string dict values
        def ensure_str_dict(dct):
            if isinstance(dct, dict):
                 return {str(k): (", ".join(v) if isinstance(v, list) else str(v)) for k, v in dct.items()}
            return {}

        summary = data.get("narrative_summary", "")
        if isinstance(summary, list):
            summary = " ".join(ensure_str_list(summary))
        summary = str(summary)

        questions = ensure_str_list(data.get("questions", []))
        speaker_intents = ensure_str_dict(data.get("speaker_intents", {}))
        
        temporal_context = data.get("temporal_context", "")
        if isinstance(temporal_context, list):
            temporal_context = ", ".join(ensure_str_list(temporal_context))
        else:
            temporal_context = str(temporal_context)
        
        entities = data.get("entities", {})
        cleaned_entities = {}
        if isinstance(entities, dict):
            for key, val in entities.items():
                # Some LLMs nest emotions or other fields inside entities
                if key in ["emotions", "interaction_pattern", "initiative", "emotional_shift", "open_loops", "speaker_intents"]:
                    continue
                
                if isinstance(val, list):
                    cleaned_entities[key] = ensure_str_list(val)
                elif isinstance(val, dict):
                    # Flatten nested dicts or just take keys as strings
                    items = []
                    for k2, v2 in val.items():
                        if isinstance(v2, list):
                            items.extend([f"{k2}: {i}" for i in ensure_str_list(v2)])
                        else:
                            items.append(f"{k2}: {v2}")
                    cleaned_entities[key] = items
                else:
                    cleaned_entities[key] = [str(val)]
        
        # If emotions was nested in entities
        emotions = data.get("emotions")
        if not emotions and isinstance(entities, dict) and "emotions" in entities:
            emotions = entities["emotions"]
        if not isinstance(emotions, dict):
            emotions = {}

        interaction_pattern = data.get("interaction_pattern")
        if not interaction_pattern and isinstance(entities, dict) and "interaction_pattern" in entities:
            interaction_pattern = entities["interaction_pattern"]
            
        initiative = data.get("initiative")
        if not initiative and isinstance(entities, dict) and "initiative" in entities:
            initiative = entities["initiative"]

        emotional_shift = data.get("emotional_shift")
        if not emotional_shift and isinstance(entities, dict) and "emotional_shift" in entities:
            emotional_shift = entities["emotional_shift"]

        open_loops = data.get("open_loops")
        if not open_loops and isinstance(entities, dict) and "open_loops" in entities:
            open_loops = entities["open_loops"]
        open_loops = ensure_str_list(open_loops)

        return (summary, questions, speaker_intents, temporal_context, cleaned_entities, 
                emotions, interaction_pattern, initiative, emotional_shift, open_loops)

    def _call_mlx(self, prompt: str) -> str:
        """Calls the MLX provider."""
        if not self.mlx_provider:
             raise ValueError("MLX Provider not initialized")
        
        messages = [{"role": "user", "content": prompt}]
        return self.mlx_provider.generate_chat(messages, max_tokens=2048, temperature=0.1)

    def _call_ollama(self, prompt: str, model: str = None) -> str:
        """Calls the Ollama API.

        Args:
            prompt: The prompt to send
            model: Which model to use (defaults to self.model)
        """
        model = model or self.model
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            # "format": "json",  # REMOVED: prevents premature truncation by some models
            "options": {
                "temperature": 0.1,
                "num_predict": 2048,  # Increased to accommodate emotions, entities, and long explanations
            }
        }

        response = requests.post(
            f"{self.config.ollama_url}/api/chat",
            json=payload,
            timeout=300
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

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

                return self._parse_enrichment_response(result)
            
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                # Log the malformed content for debugging
                try:
                    with open("malformed_json_debug.log", "a", encoding="utf-8") as debug_f:
                        debug_f.write(f"--- Chunk {chunk.chunk_id} (Attempt {attempt+1}) [Internal] ---\n")
                        debug_f.write(f"Error: {e}\n")
                        debug_f.write(f"Content:\n{result}\n")
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