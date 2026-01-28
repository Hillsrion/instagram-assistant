"""
Enrichisseur de chunks utilisant un LLM pour générer des résumés narratifs
et des questions hypothétiques (techniques avancées de RAG).
"""
import json
import requests
from typing import List, Optional, Tuple, Dict
from .config import Config, default_config
from .chunker import Chunk

ENRICH_PROMPT = """Tu es un analyseur de conversations (STRICT, basé sur le texte uniquement).

ANALYSE CETTE CONVERSATION ET GÉNÈRE JSON :

1. **RÉSUMÉ** : 1 phrase max, l'action/intention/résultat
2. **QUESTIONS** : 3 questions précises que cet extrait répond (ce qu'un utilisateur demanderait)
3. **INTENTIONS** : Pour chaque participant → son objectif principal (une phrase max)
4. **CONTEXTE TEMPOREL** : Moment/période (ex: "avant X", "durant vacances")
5. **ENTITÉS** : Éléments mentionnés dans le texte SEULEMENT:
   - locations, people (hors participants), media, events
   - ZÉRO hallucinations, ZÉRO inferences
6. **ÉMOTIONS** : Ambiance générale de l'échange:
   - dominant: émotion principale (basée sur le texte)
   - tone: ton général (léger, sérieux, playful, etc)
   - tension_level: low/medium/high

CONVERSATION:
{content}

RÈGLES STRICTES:
- Format JSON obligatoire, ZÉRO texte avant ou après
- ZÉRO détails non présents dans le texte
- Sois concis et direct

JSON OBLIGATOIRE:
{{
  "narrative_summary": "Ismaël et Marie organisent un shooting photo à Lyon",
  "questions": ["Quand a lieu le shooting ?", "Qui participe ?", "Où se passe l'événement ?"],
  "speaker_intents": {{"Ismaël": "organiser le shooting", "Marie": "confirmer sa venue"}},
  "temporal_context": "pendant la préparation d'un événement",
  "entities": {{"locations": ["Lyon", "Parc de la Tête d'Or"], "people": ["Sarah"], "media": [], "events": ["shooting photo"]}},
  "emotions": {{"dominant": "excitation", "tone": "léger", "tension_level": "low"}}
}}
"""

class ChunkEnricher:
    """Utilise un LLM (via Ollama) pour enrichir les métadonnées des chunks."""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        # Modèle léger recommandé pour l'indexation de masse
        self.model = self.config.llm_model 
        
    def enrich_chunk(self, chunk: Chunk) -> Tuple[str, List[str], Dict[str, str], str, Dict[str, List[str]], Dict[str, str]]:
        """
        Génère un résumé narratif, des questions, les intentions, le contexte temporel, les entités et les émotions pour un chunk.

        Returns:
            (narrative_summary, hypothetical_questions, speaker_intents, temporal_context, entities, emotions)
        """
        # Limiter la taille du texte pour éviter de saturer le context window du petit modèle
        content_preview = chunk.content[:4000]

        prompt = ENRICH_PROMPT.format(content=content_preview)

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json", # Demander du JSON à Ollama
            "options": {
                "temperature": 0.1,
                "num_predict": 2048,  # Augmenté pour accommoder les émotions, entités et explications longues
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

            # Nettoyage de la réponse (au cas où le LLM ajoute des markdown code blocks)
            cleaned_result = result.strip()
            if cleaned_result.startswith("```json"):
                cleaned_result = cleaned_result[7:]
            if cleaned_result.startswith("```"):
                cleaned_result = cleaned_result[3:]
            if cleaned_result.endswith("```"):
                cleaned_result = cleaned_result[:-3]
            cleaned_result = cleaned_result.strip()

            # Parser le JSON de réponse
            if not cleaned_result:
                print(f"[ENRICH LOG] Empty response for chunk {chunk.chunk_id}")
                return "", [], {}, "", {}, {}

            data = json.loads(cleaned_result)
            summary = data.get("narrative_summary", "")
            questions = data.get("questions", [])
            speaker_intents = data.get("speaker_intents", {})
            temporal_context = data.get("temporal_context", "")
            entities = data.get("entities", {})
            emotions = data.get("emotions", {})

            return summary, questions, speaker_intents, temporal_context, entities, emotions

        except json.JSONDecodeError as e:
            print(f"⚠️ Erreur décodage JSON pour chunk {chunk.chunk_id}: {e}")
            print(f"[ENRICH LOG] Failed to parse JSON: {e}")
            if 'cleaned_result' in locals():
                print(f"[ENRICH LOG] Cleaned result:\n{cleaned_result[:500]}...")
            elif 'result' in locals():
                 print(f"[ENRICH LOG] Raw result:\n{result[:500]}...")
            return "", [], {}, "", {}, {}
        except Exception as e:
            # En cas d'erreur, on retourne des valeurs vides (fallback sur le résumé statistique)
            print(f"⚠️ Erreur enrichissement chunk {chunk.chunk_id}: {e}")
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
        Enrichit une liste de chunks avec reprise sur erreur.
        
        Args:
            chunks: Liste des chunks à traiter
            progress_callback: Fonction(current, total) appelée à chaque étape
            save_callback: Fonction() appelée périodiquement pour sauvegarder
            save_interval: Sauvegarder tous les X chunks
        """
        print(f"🔄 Démarrage de l'enrichissement par lots (Sauvegarde tous les {save_interval} items)")
        
        for i, chunk in enumerate(chunks):
            # Si déjà enrichi (reprise), on saute
            # Note: Si on ajoute de nouveaux champs (comme entities), il faudrait idéalement forcer la réindexation
            # ou vérifier si le champ est manquant. Ici on assume que l'utilisateur fera --reset s'il veut les nouveaux champs.
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
            
            # Callback de progrès
            if progress_callback:
                progress_callback(i + 1, len(chunks))
            
            # Sauvegarde périodique
            if save_callback and (i + 1) % save_interval == 0:
                print("   💾 Sauvegarde intermédiaire...")
                save_callback()
                
        # Sauvegarde finale
        if save_callback:
            save_callback()
            
        return chunks
