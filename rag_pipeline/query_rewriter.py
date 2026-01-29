"""
Query Rewriting Module.
Transforms a vague or context-dependent user query into a precise, autonomous query.
"""
import requests
import json
from typing import List, Dict, Optional
from .config import Config

REWRITE_PROMPT = """Tu es un expert en reformulation de requêtes pour un moteur de recherche.

TÂCHE: Réécrire la question pour qu'elle soit:
1. Autonome (compréhensible seule, sans historique)
2. Précise (mots réels, pas de pronoms vagues)
3. Optimisée pour la recherche (mots-clés pertinents)

HISTORIQUE:
{history}

QUESTION:
{query}

RÈGLES STRICTES:
- RÉPONSE UNIQUEMENT: la question réécrite
- ZÉRO commentaires, ZÉRO guillemets
- Si déjà claire → renvoie telle quelle
- Sois bref et direct
"""

class QueryRewriter:
    """Rewrites user queries to improve retrieval."""

    def __init__(self, config: Config):
        self.config = config
        self.model = self.config.llm_model_fast

    def rewrite(self, query: str, history: List[Dict[str, str]]) -> str:
        """
        Rewrites the query based on history.

        Args:
            query: Current user question
            history: List of dicts {"role": "user/assistant", "content": "..."}

        Returns:
            Rewritten query (str)
        """
        # If no history, no need to rewrite (except for simple clarification, but less critical)
        if not history:
            return query

        # Limit history to last 3 exchanges to avoid pollution
        recent_history = history[-6:]
        formatted_history = ""
        for msg in recent_history:
            role = "Utilisateur" if msg['role'] == 'user' else "Assistant"
            formatted_history += f"{role}: {msg['content']}\n"

        prompt = REWRITE_PROMPT.format(history=formatted_history, query=query)

        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {
                        "temperature": 0.0,  # Deterministic
                        "num_predict": 64
                    }
                },
                timeout=10.0  # Short timeout
            )
            
            if response.status_code == 200:
                rewritten = response.json()["message"]["content"].strip()
                # Basic cleanup if LLM is chatty
                if rewritten.startswith('"') and rewritten.endswith('"'):
                    rewritten = rewritten[1:-1]
                return rewritten
            
        except Exception as e:
            print(f"⚠️ Query Rewriting Error: {e}")
            
        return query