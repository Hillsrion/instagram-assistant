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
Analyse l'extrait de conversation Instagram ci-dessous et génère cinq éléments :

1. RÉSUMÉ NARRATIF : Une seule phrase qui décrit l'action principale, l'intention et le résultat de l'échange.
2. QUESTIONS HYPOTHÉTIQUES : Liste 3 questions précises auxquelles cet extrait de conversation répond exactement. Ces questions doivent ressembler à ce qu'un utilisateur pourrait demander à un assistant.
3. INTENTIONS DES PARTICIPANTS : Pour chaque participant actif, décris en quelques mots son intention ou objectif principal dans cet échange.
4. CONTEXTE TEMPOREL : Décris le moment ou la période de cet échange de manière sémantique (ex: "avant l'obtention du visa", "pendant les vacances d'été", "après la rupture").
5. ÉMOTIONS : Analyse l'ambiance émotionnelle globale de l'échange avec trois dimensions :
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
        
    def enrich_chunk(self, chunk: Chunk) -> Tuple[str, List[str], Dict[str, str], str, Dict[str, str]]:
        """
        Génère un résumé narratif, des questions, les intentions, le contexte temporel et les émotions pour un chunk.

        Returns:
            (narrative_summary, hypothetical_questions, speaker_intents, temporal_context, emotions)
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
                "num_predict": 1024,  # Augmenté pour accommoder les émotions
            }
        }

        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()["message"]["content"]

            # Parser le JSON de réponse
            data = json.loads(result)
            summary = data.get("narrative_summary", "")
            questions = data.get("questions", [])
            speaker_intents = data.get("speaker_intents", {})
            temporal_context = data.get("temporal_context", "")
            emotions = data.get("emotions", {})

            return summary, questions, speaker_intents, temporal_context, emotions

        except Exception as e:
            # En cas d'erreur, on retourne des valeurs vides (fallback sur le résumé statistique)
            print(f"⚠️ Erreur enrichissement chunk {chunk.chunk_id}: {e}")
            return "", [], {}, "", {}

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
            if chunk.narrative_summary and chunk.hypothetical_questions:
                if progress_callback:
                    progress_callback(i + 1, len(chunks))
                continue

            summary, questions, speaker_intents, temporal_context, emotions = self.enrich_chunk(chunk)
            chunk.narrative_summary = summary
            chunk.hypothetical_questions = questions
            chunk.speaker_intents = speaker_intents
            chunk.temporal_context = temporal_context
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
