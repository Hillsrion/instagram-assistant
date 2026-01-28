"""
Analyseur de requêtes consolidé (Omni-Prompt).
Fusionne la réécriture, la détection d'intention et l'extraction de dates en un seul appel LLM.
"""
import json
import requests
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from .config import Config, default_config

@dataclass
class AnalysisResult:
    """Résultat consolidé de l'analyse d'une requête."""
    rewritten_query: str
    intent: str
    top_k: int
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    use_reranking: bool = True
    expand_context: bool = True

class QueryAnalyzer:
    """Analyseur unique pour réduire la latence du pipeline RAG."""

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.model = self.config.llm_model
        self.today = datetime.now()

    def analyze(self, query: str, history: List[Dict[str, str]]) -> AnalysisResult:
        """
        Effectue une analyse complète de la requête en un seul appel LLM.
        """
        # Formater l'historique récent
        recent_history = history[-6:] if history else []
        formatted_history = ""
        for msg in recent_history:
            role = "Utilisateur" if msg['role'] == 'user' else "Assistant"
            formatted_history += f"{role}: {msg['content']}\n"

        today_str = self.today.strftime('%A %d %B %Y')
        iso_str = self.today.strftime('%Y-%m-%d')

        system_prompt = f"""Tu es un assistant de pré-traitement pour un système de recherche (RAG).
Aujourd'hui nous sommes le : {today_str} (ISO: {iso_str}).

Ta mission est de transformer la dernière question de l'utilisateur en une structure de recherche optimisée.

1. REFORMULATION (rewritten_query) :
   - Rends la question autonome (compréhensible sans l'historique).
   - Remplace les pronoms (il, ça, eux, ce moment-là) par les entités réelles mentionnées dans l'historique.
   - Optimise pour la recherche de mots-clés.

2. INTENTION (intent) :
   - 'specific_fact' : Recherche d'un fait précis (date, lieu, nom, événement ponctuel).
   - 'broad_summary' : Demande de résumé, d'ambiance, de thématiques générales ou d'évolution d'une relation.
   - 'complex_reasoning' : Question nécessitant de croiser plusieurs informations ou d'analyser en profondeur.

3. DATES (date_range) :
   - Extrais la période mentionnée explicitement ou implicitement.
   - 'été dernier' -> 1er juin au 31 août de l'année précédente.
   - 'le mois dernier' -> calculer par rapport à aujourd'hui.
   - Retourne null si aucune période n'est mentionnée.

RÉPONDS UNIQUEMENT AU FORMAT JSON SUIVANT :
{{
  "rewritten_query": "la question reformulée",
  "intent": "specific_fact|broad_summary|complex_reasoning",
  "date_range": {{
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD"
  }}
}}"""

        user_content = f"HISTORIQUE :\n{formatted_history}\n\nDERNIÈRE QUESTION : {query}"

        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.0,
                        "num_predict": 256
                    }
                },
                timeout=15.0
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            data = json.loads(content)

            # Mapping des paramètres selon l'intention
            intent = data.get("intent", "complex_reasoning")
            params = self._get_params_for_intent(intent)
            
            date_range = data.get("date_range") or {}
            
            return AnalysisResult(
                rewritten_query=data.get("rewritten_query", query),
                intent=intent,
                top_k=params["top_k"],
                use_reranking=params["use_reranking"],
                expand_context=params["expand_context"],
                date_start=date_range.get("start"),
                date_end=date_range.get("end")
            )

        except Exception as e:
            print(f"⚠️ Erreur Query Analysis: {e}")
            # Fallback sur les valeurs par défaut
            return AnalysisResult(
                rewritten_query=query,
                intent="complex_reasoning",
                top_k=self.config.top_k
            )

    def _get_params_for_intent(self, intent: str) -> Dict[str, Any]:
        """Retourne les paramètres de recherche optimisés pour une intention."""
        if intent == "specific_fact":
            return {
                "top_k": 5,
                "use_reranking": True,
                "expand_context": False
            }
        elif intent == "broad_summary":
            return {
                "top_k": 15,
                "use_reranking": False, # Trop de docs, on privilégie la masse
                "expand_context": True
            }
        else: # complex_reasoning ou fallback
            return {
                "top_k": 10,
                "use_reranking": True,
                "expand_context": True
            }
