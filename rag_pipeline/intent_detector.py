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
        system_prompt = """Tu es un classifieur d'intentions (STRICT, ultra-concis).

CLASSE LA QUESTION DANS UNE CATÉGORIE:

1. 'specific_fact' = Fait précis (date, lieu, nom, chiffre)
2. 'broad_summary' = Résumé/ambiance/évolution d'un sujet large
3. 'complex_reasoning' = Croiser plusieurs infos/points de vue

RÉPONSE OBLIGATOIRE:
- UNE SEULE LIGNE
- NOM DE CATÉGORIE UNIQUEMENT
- ZÉRO texte supplémentaire"""

        try:
            # Appel direct à Ollama
            payload = {
                "model": self.config.llm_model_fast,
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
