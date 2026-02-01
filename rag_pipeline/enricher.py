"""
Chunk enricher using an LLM to generate narrative summaries
and hypothetical questions (advanced RAG techniques).
"""
import json
import requests
from typing import List, Optional, Tuple, Dict
from .config import Config, default_config
from .chunker import Chunk

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
    """Uses an LLM (via Ollama or MLX) to enrich chunk metadata."""
    
    def __init__(self, config: Config = None, provider: str = "ollama"):
        self.config = config or default_config
        self.provider = provider
        # Lightweight model recommended for mass indexing
        self.model = self.config.llm_model
        self.mlx_provider = None
        
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
        
    def enrich_chunk(self, chunk: Chunk) -> Tuple[str, List[str], Dict[str, str], str, Dict[str, List[str]], Dict[str, str], Optional[str], Optional[str], Optional[str], Optional[List[str]]]:
        """
        Generates narrative summary, questions, intents, temporal context, entities, emotions and social dynamics for a chunk.

        Returns:
            (summary, questions, speaker_intents, temporal_context, entities, emotions, interaction_pattern, initiative, emotional_shift, open_loops)
        """
        # Limit text size removed as per user request (128k context available)
        content_preview = chunk.content

        prompt = ENRICH_PROMPT.format(
            content=content_preview,
            max_questions=self.config.max_questions
        )

        try:
            result = ""
            if self.provider == "mlx":
                result = self._call_mlx(prompt)
            else:
                result = self._call_ollama(prompt)

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
            temporal_context = data.get("temporal_context", "")
            
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

            return summary, questions, speaker_intents, temporal_context, entities, emotions, interaction_pattern, initiative, emotional_shift, open_loops

        except json.JSONDecodeError as e:
            print(f"⚠️ JSON decoding error for chunk {chunk.chunk_id}: {e}")
            print(f"[ENRICH LOG] Failed to parse JSON: {e}")
            if 'cleaned_result' in locals():
                print(f"[ENRICH LOG] Cleaned result:\n{cleaned_result[:500]}...")
            elif 'result' in locals():
                 print(f"[ENRICH LOG] Raw result:\n{result[:500]}...")
            return "", [], {}, "", {}, {}, None, None, None, None
        except Exception as e:
            # In case of error, return empty values (fallback to statistical summary)
            print(f"⚠️ Enrichment error chunk {chunk.chunk_id}: {e}")
            print(f"[ENRICH LOG] Error: {e}")
            if 'result' in locals():
                print(f"[ENRICH LOG] Raw result:\n{result[:500]}...")
            return "", [], {}, "", {}, {}, None, None, None, None

    def _call_mlx(self, prompt: str) -> str:
        """Calls the MLX provider."""
        if not self.mlx_provider:
             raise ValueError("MLX Provider not initialized")
        
        messages = [{"role": "user", "content": prompt}]
        return self.mlx_provider.generate_chat(messages, max_tokens=2048, temperature=0.1)

    def _call_ollama(self, prompt: str) -> str:
        """Calls the Ollama API."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json", # Request JSON from Ollama
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
                
        # Final save
        if save_callback:
            save_callback()
            
        return chunks