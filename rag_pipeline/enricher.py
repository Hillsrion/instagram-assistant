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
2. **QUESTIONS** : 3 questions précises que cet extrait répond (ce qu'un utilisateur demanderait)
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
  "questions": ["<question 1>", "<question 2>", "<question 3>"],
  "speaker_intents": {{
    "<participant>": "<son intention>"
  }},
  "temporal_context": "<moment ou période>",
  "entities": {{ "locations": [], "people": [], "media": [], "events": [] }},
  "emotions": {{ "dominant": "<émotion>", "tone": "<ton>", "tension_level": "low|medium|high" }}
}}
"""

class ChunkEnricher:
    """Uses an LLM (via Ollama) to enrich chunk metadata."""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        # Lightweight model recommended for mass indexing
        self.model = self.config.llm_model 
        
    def enrich_chunk(self, chunk: Chunk) -> Tuple[str, List[str], Dict[str, str], str, Dict[str, List[str]], Dict[str, str]]:
        """
        Generates narrative summary, questions, intents, temporal context, entities, and emotions for a chunk.

        Returns:
            (narrative_summary, hypothetical_questions, speaker_intents, temporal_context, entities, emotions)
        """
        # Limit text size to avoid saturating context window of small models
        content_preview = chunk.content[:4000]

        prompt = ENRICH_PROMPT.format(content=content_preview)

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

        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            result = response.json()["message"]["content"]

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
                return "", [], {}, "", {}, {}

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

            return summary, questions, speaker_intents, temporal_context, entities, emotions

        except json.JSONDecodeError as e:
            print(f"⚠️ JSON decoding error for chunk {chunk.chunk_id}: {e}")
            print(f"[ENRICH LOG] Failed to parse JSON: {e}")
            if 'cleaned_result' in locals():
                print(f"[ENRICH LOG] Cleaned result:\n{cleaned_result[:500]}...")
            elif 'result' in locals():
                 print(f"[ENRICH LOG] Raw result:\n{result[:500]}...")
            return "", [], {}, "", {}, {}
        except Exception as e:
            # In case of error, return empty values (fallback to statistical summary)
            print(f"⚠️ Enrichment error chunk {chunk.chunk_id}: {e}")
            print(f"[ENRICH LOG] Error: {e}")
            if 'result' in locals():
                print(f"[ENRICH LOG] Raw result:\n{result[:500]}...")
            return "", [], {}, "", {}, {}

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

            summary, questions, speaker_intents, temporal_context, entities, emotions = self.enrich_chunk(chunk)
            chunk.narrative_summary = summary
            chunk.hypothetical_questions = questions
            chunk.speaker_intents = speaker_intents
            chunk.temporal_context = temporal_context
            chunk.entities = entities
            chunk.emotions = emotions
            
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