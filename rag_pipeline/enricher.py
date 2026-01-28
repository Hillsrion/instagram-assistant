"""
Enrichisseur de chunks utilisant un LLM pour générer des résumés narratifs
et des questions hypothétiques (techniques avancées de RAG).
"""
import json
import requests
from typing import List, Optional, Tuple, Dict
from .config import Config, default_config
from .chunker import Chunk

ENRICH_PROMPT = """Tu es un expert en analyse de conversations.
Analyse l'extrait de conversation Instagram ci-dessous et génère six éléments :

1. RÉSUMÉ NARRATIF : Une seule phrase qui décrit l'action principale, l'intention et le résultat de l'échange.
2. QUESTIONS HYPOTHÉTIQUES : Liste 3 questions précises auxquelles cet extrait de conversation répond exactement. Ces questions doivent ressembler à ce qu'un utilisateur pourrait demander à un assistant.
3. INTENTIONS DES PARTICIPANTS : Pour chaque participant actif, décris en quelques mots son intention ou objectif principal dans cet échange.
4. CONTEXTE TEMPOREL : Décris le moment ou la période de cet échange de manière sémantique (ex: "avant l'obtention du visa", "pendant les vacances d'été", "après la rupture").
5. ENTITÉS NOMMÉES : Extrais les éléments importants mentionnés :
   - locations : villes, pays, restaurants, lieux spécifiques
   - people : personnes mentionnées (hors participants)
   - media : films, séries, livres, jeux, chansons
   - events : fêtes, concerts, réunions, voyages
6. ÉMOTIONS : Analyse l'ambiance émotionnelle globale de l'échange avec trois dimensions :
   - dominant : l'émotion principale (joie, tristesse, colère, peur, surprise, excitation, frustration, affection, inquiétude, soulagement, etc.)
   - tone : le ton général (léger, sérieux, playful, tendu, intime, formel, sarcastique, etc.)
   - tension_level : niveau de tension (low, medium, high)

CONVERSATION :
{content}

RÉPONDS STRICTEMENT AU FORMAT JSON SUIVANT :
{{
  "narrative_summary": "La phrase de résumé ici",
  "questions": [
    "Question 1 ?",
    "Question 2 ?",
    "Question 3 ?"
  ],
  "speaker_intents": {{
    "Participant1": "son intention principale",
    "Participant2": "son intention principale"
  }},
  "temporal_context": "description sémantique du moment",
  "entities": {{
    "locations": ["Paris", "McDo"],
    "people": ["Sarah", "Thomas"],
    "media": ["Inception", "GTA VI"],
    "events": ["Anniversaire", "Noël"]
  }},
  "emotions": {{
    "dominant": "émotion principale",
    "tone": "ton général",
    "tension_level": "low/medium/high"
  }}
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
