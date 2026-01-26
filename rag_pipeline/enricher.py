"""
Enrichisseur de chunks utilisant un LLM pour générer des résumés narratifs
et des questions hypothétiques (techniques avancées de RAG).
"""
import json
import requests
from typing import List, Optional, Tuple
from .config import Config, default_config
from .chunker import Chunk

ENRICH_PROMPT = """Tu es un expert en analyse de conversations.
Analyse l'extrait de conversation Instagram ci-dessous et génère deux éléments :

1. RÉSUMÉ NARRATIF : Une seule phrase qui décrit l'action principale, l'intention et le résultat de l'échange.
2. QUESTIONS HYPOTHÉTIQUES : Liste 3 questions précises auxquelles cet extrait de conversation répond exactement. Ces questions doivent ressembler à ce qu'un utilisateur pourrait demander à un assistant.

CONVERSATION :
{content}

RÉPONDS STRICTEMENT AU FORMAT JSON SUIVANT :
{{
  "narrative_summary": "La phrase de résumé ici",
  "questions": [
    "Question 1 ?",
    "Question 2 ?",
    "Question 3 ?"
  ]
}}
"""

class ChunkEnricher:
    """Utilise un LLM (via Ollama) pour enrichir les métadonnées des chunks."""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        # Modèle léger recommandé pour l'indexation de masse
        self.model = self.config.llm_model 
        
    def enrich_chunk(self, chunk: Chunk) -> Tuple[str, List[str]]:
        """
        Génère un résumé narratif et des questions pour un chunk.
        
        Returns:
            (narrative_summary, hypothetical_questions)
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
                "num_predict": 512,
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
            
            return summary, questions
            
        except Exception as e:
            # En cas d'erreur, on retourne des valeurs vides (fallback sur le résumé statistique)
            print(f"⚠️ Erreur enrichissement chunk {chunk.chunk_id}: {e}")
            return "", []

    def enrich_batch(self, chunks: List[Chunk], progress_callback=None) -> List[Chunk]:
        """Enrichit une liste de chunks."""
        for i, chunk in enumerate(chunks):
            if not chunk.narrative_summary or not chunk.hypothetical_questions:
                summary, questions = self.enrich_chunk(chunk)
                chunk.narrative_summary = summary
                chunk.hypothetical_questions = questions
            
            if progress_callback:
                progress_callback(i + 1, len(chunks))
                
        return chunks
