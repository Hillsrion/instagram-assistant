"""
Module de réécriture de requêtes (Query Rewriting).
Transforme une requête utilisateur vague ou dépendante du contexte en une requête autonome précise.
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
    """Réécrit les requêtes utilisateur pour améliorer le retrieval."""

    def __init__(self, config: Config):
        self.config = config
        self.model = self.config.llm_model

    def rewrite(self, query: str, history: List[Dict[str, str]]) -> str:
        """
        Réécrit la requête en fonction de l'historique.

        Args:
            query: La question actuelle de l'utilisateur
            history: Liste de dicts {"role": "user/assistant", "content": "..."}

        Returns:
            La requête réécrite (str)
        """
        # Si pas d'historique, pas besoin de réécrire (sauf pour clarification simple, mais moins critique)
        if not history:
            return query

        # Limiter l'historique aux 3 derniers échanges pour ne pas polluer
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
                        "temperature": 0.0,  # Déterminisme
                        "num_predict": 64
                    }
                },
                timeout=10.0  # Timeout court
            )
            
            if response.status_code == 200:
                rewritten = response.json()["message"]["content"].strip()
                # Nettoyage basique si le LLM est bavard
                if rewritten.startswith('"') and rewritten.endswith('"'):
                    rewritten = rewritten[1:-1]
                return rewritten
            
        except Exception as e:
            print(f"⚠️ Erreur Query Rewriting: {e}")
            
        return query
