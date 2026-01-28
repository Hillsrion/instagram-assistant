"""
Détecteur d'intention pour optimiser les paramètres du RAG.
Utilise le LLM pour classifier la requête utilisateur.
"""
import requests
from enum import Enum
from typing import Dict, Any, Optional

from .config import Config, default_config


class SearchIntent(str, Enum):
    """Intention de recherche pour optimiser le retrieval."""
    SPECIFIC_FACT = "specific_fact"      # Cherche une info précise -> top_k faible
    BROAD_SUMMARY = "broad_summary"      # Cherche à comprendre un sujet large -> top_k élevé
    COMPLEX_REASONING = "complex_reasoning" # Nécessite plusieurs points de vue -> top_k moyen


class IntentDetector:
    """Analyse l'intention de l'utilisateur pour adapter le RAG."""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
    
    def detect_intent(self, query: str) -> Dict[str, Any]:
        """
        Analyse la requête et retourne les paramètres recommandés.
        """
        system_prompt = """Tu es un routeur de base de données expert.
Analyse la demande de l'utilisateur et classe-la dans une des catégories suivantes :
- 'specific_fact' : L'utilisateur cherche un fait précis (date, lieu, nom, quantité spécifique).
- 'broad_summary' : L'utilisateur veut un résumé, une ambiance, une évolution ou comprendre un sujet large.
- 'complex_reasoning' : La question nécessite de croiser plusieurs informations ou points de vue.

Réponds UNIQUEMENT par la catégorie (sans explication)."""

        try:
            # Appel direct à Ollama
            payload = {
                "model": self.config.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 10,
                }
            }
            
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            intent_str = response.json()["message"]["content"].strip().lower()
            
            # Mapping des paramètres
            if "specific_fact" in intent_str:
                return {
                    "intent": SearchIntent.SPECIFIC_FACT,
                    "top_k": 3,
                    "use_reranking": True,
                    "expand_context": False
                }
            elif "broad_summary" in intent_str:
                return {
                    "intent": SearchIntent.BROAD_SUMMARY,
                    "top_k": 12,
                    "use_reranking": False, # Trop de docs pour reranking efficace/rapide
                    "expand_context": True
                }
            elif "complex_reasoning" in intent_str:
                return {
                    "intent": SearchIntent.COMPLEX_REASONING,
                    "top_k": 8,
                    "use_reranking": True,
                    "expand_context": True
                }
            else:
                return {
                    "intent": SearchIntent.COMPLEX_REASONING,
                    "top_k": self.config.top_k,
                    "use_reranking": True,
                    "expand_context": True
                }
                
        except Exception as e:
            # Fallback silencieux sur les paramètres par défaut
            return {
                "intent": None,
                "top_k": self.config.top_k,
                "use_reranking": True,
                "expand_context": True,
                "error": str(e)
            }
