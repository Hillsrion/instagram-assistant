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
from typing import List, Optional, Tuple, Dict
from .config import Config, default_config
from .chunker import Chunk
from .complexity_analyzer import ChunkComplexityAnalyzer
from .enrichment_log import EnrichmentLogger

# Prompt kept in French as it processes French data
ENRICH_PROMPT = """Tu es un analyseur de conversations (STRICT, basé sur le texte uniquement).

ANALYSE CETTE CONVERSATION ET GÉNÈRE JSON :

1. **RÉSUMÉ** : 1 phrase max, l'action/intention/résultat
2. **QUESTIONS** : 1 à {max_questions} questions précises que cet extrait répond, selon la densité (ce qu'un utilisateur demanderait)
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

        try:
            result = ""
            selected_model = self.model
            complexity_score = 0.0
            complexity_category = "unknown"
            metrics_breakdown = None

            if self.provider == "mlx":
                result = self._call_mlx(prompt)
            else:
                # Select model based on complexity routing
                if self.enable_routing:
                    analysis = self.complexity_analyzer.analyze(chunk)
                    complexity_score = analysis.score
                    complexity_category = analysis.category
                    metrics_breakdown = analysis.breakdown
                    selected_model = self._select_model_for_chunk(chunk)
                    self._ensure_model_loaded(selected_model)
                else:
                    selected_model = self.model

                result = self._call_ollama(prompt, model=selected_model)

            # Clean response (in case LLM adds markdown code blocks)
            cleaned_result = result.strip()
            if cleaned_result.startswith("```json"):
                cleaned_result = cleaned_result[7:]
            if cleaned_result.startswith("```"):
                cleaned_result = cleaned_result[3:]
            if cleaned_result.endswith("```"):
                cleaned_result = cleaned_result[:-3]
            cleaned_result = cleaned_result.strip()

            # Parse response JSON
            if not cleaned_result:
                print(f"[ENRICH LOG] Empty response for chunk {chunk.chunk_id}")
                return "", [], {}, "", {}, {}, None, None, None, None

            data = json.loads(cleaned_result)
            summary = data.get("narrative_summary", "")
            
            questions = data.get("questions", [])
            if isinstance(questions, list):
                questions = [str(q) if not isinstance(q, str) else q for q in questions]
            
            speaker_intents = data.get("speaker_intents", {})
            if isinstance(speaker_intents, dict):
                # Ensure all values are strings (some LLMs return lists)
                speaker_intents = {
                    str(k): (", ".join(v) if isinstance(v, list) else str(v))
                    for k, v in speaker_intents.items()
                }
            
            temporal_context = data.get("temporal_context", "")
            if isinstance(temporal_context, list):
                temporal_context = ", ".join(temporal_context)
            else:
                temporal_context = str(temporal_context)
            
            entities = data.get("entities", {})
            if isinstance(entities, dict):
                for key, val in entities.items():
                    if isinstance(val, list):
                         entities[key] = [str(v) if not isinstance(v, str) else v for v in val]

            emotions = data.get("emotions", {})
            
            interaction_pattern = data.get("interaction_pattern")
            initiative = data.get("initiative")
            emotional_shift = data.get("emotional_shift")
            open_loops = data.get("open_loops")
            if isinstance(open_loops, list):
                open_loops = [str(l) if not isinstance(l, str) else l for l in open_loops]

            # Log the decision
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

            return summary, questions, speaker_intents, temporal_context, entities, emotions, interaction_pattern, initiative, emotional_shift, open_loops

        except json.JSONDecodeError as e:
            enrichment_time_ms = (time.time() - start_time) * 1000
            print(f"⚠️ JSON decoding error for chunk {chunk.chunk_id}: {e}")
            print(f"[ENRICH LOG] Failed to parse JSON: {e}")
            if 'cleaned_result' in locals():
                print(f"[ENRICH LOG] Cleaned result:\n{cleaned_result[:500]}...")
            elif 'result' in locals():
                 print(f"[ENRICH LOG] Raw result:\n{result[:500]}...")

            # Log the failed decision
            if self.enrichment_logger and self.enable_routing:
                self.enrichment_logger.log_decision(
                    chunk_id=chunk.chunk_id,
                    complexity_score=complexity_score if 'complexity_score' in locals() else 0.0,
                    complexity_category=complexity_category if 'complexity_category' in locals() else "unknown",
                    selected_model=selected_model if 'selected_model' in locals() else self.model,
                    enrichment_time_ms=enrichment_time_ms,
                    message_count=chunk.message_count or 0,
                    participant_count=len(chunk.participants) if chunk.participants else 0,
                    reason="JSON decode error"
                )
            return "", [], {}, "", {}, {}, None, None, None, None
        except Exception as e:
            enrichment_time_ms = (time.time() - start_time) * 1000
            # In case of error, return empty values (fallback to statistical summary)
            print(f"⚠️ Enrichment error chunk {chunk.chunk_id}: {e}")
            print(f"[ENRICH LOG] Error: {e}")
            if 'result' in locals():
                print(f"[ENRICH LOG] Raw result:\n{result[:500]}...")

            # Log the failed decision
            if self.enrichment_logger and self.enable_routing:
                self.enrichment_logger.log_decision(
                    chunk_id=chunk.chunk_id,
                    complexity_score=complexity_score if 'complexity_score' in locals() else 0.0,
                    complexity_category=complexity_category if 'complexity_category' in locals() else "unknown",
                    selected_model=selected_model if 'selected_model' in locals() else self.model,
                    enrichment_time_ms=enrichment_time_ms,
                    message_count=chunk.message_count or 0,
                    participant_count=len(chunk.participants) if chunk.participants else 0,
                    reason=f"Exception: {str(e)[:50]}"
                )
            return "", [], {}, "", {}, {}, None, None, None, None

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
            "format": "json",  # Request JSON from Ollama
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

    def enrich_batch(
        self,
        chunks: List[Chunk],
        progress_callback=None,
        save_callback=None,
        save_interval: int = 20
    ) -> List[Chunk]:
        """
        Enriches a list of chunks with error recovery.

        Args:
            chunks: List of chunks to process
            progress_callback: Function(current, total) called at each step
            save_callback: Function() called periodically to save
            save_interval: Save every X chunks
        """
        print(f"🔄 Starting batch enrichment (Saving every {save_interval} items)")
        if self.enable_routing:
            print(f"   📊 Complexity routing enabled ({self.loading_strategy} strategy)")

        for i, chunk in enumerate(chunks):
            # If already enriched (resume), skip
            # Note: If we add new fields (like entities), ideally force re-indexing
            # or check if field is missing. Here we assume user runs --reset if they want new fields.
            if chunk.narrative_summary and chunk.hypothetical_questions and chunk.entities:
                if progress_callback:
                    progress_callback(i + 1, len(chunks))
                continue

            summary, questions, speaker_intents, temporal_context, entities, emotions, interaction_pattern, initiative, emotional_shift, open_loops = self.enrich_chunk(chunk)
            chunk.narrative_summary = summary
            chunk.hypothetical_questions = questions
            chunk.speaker_intents = speaker_intents
            chunk.temporal_context = temporal_context
            chunk.entities = entities
            chunk.emotions = emotions

            chunk.interaction_pattern = interaction_pattern
            chunk.initiative = initiative
            chunk.emotional_shift = emotional_shift
            chunk.open_loops = open_loops

            # Progress callback
            if progress_callback:
                progress_callback(i + 1, len(chunks))

            # Periodic save
            if save_callback and (i + 1) % save_interval == 0:
                print("   💾 Intermediate save...")
                save_callback()
                # Save enrichment logs too
                if self.enrichment_logger:
                    self.enrichment_logger.save()

        # Final save
        if save_callback:
            save_callback()

        # Save and export enrichment logs
        if self.enrichment_logger:
            self.enrichment_logger.save()
            self.enrichment_logger.export_csv()
            self.enrichment_logger.print_summary()

        # Print routing statistics if enabled
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