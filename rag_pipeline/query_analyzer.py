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
from .logger import get_logger

logger = get_logger()

@dataclass
class AnalysisResult:
    """Résultat consolidé de l'analyse d'une requête."""
    rewritten_query: str
    intent: str
    mode: str # 'retrieval' ou 'analytics'
    top_k: int
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    use_reranking: bool = True
    expand_context: bool = True

class QueryAnalyzer:
    """Analyseur unique pour réduire la latence du pipeline RAG."""

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.model = self.config.llm_model_fast
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

        system_prompt = f"""Tu es un pré-processeur RAG (STRICT, JSON uniquement).
Aujourd'hui: {today_str} (ISO: {iso_str}).

Transforme la question en structure de recherche optimisée.

1. MODE (DÉCISION CRITIQUE):

   ✅ 'analytics' = COMPTAGE/STATISTIQUES UNIQUEMENT
   Exemples ANALYTICS:
   - "Combien j'ai de messages ?" → compter le total
   - "Nombre de messages avec Marie ?" → compter par contact
   - "Combien de fois on a parlé de sport ?" → compter des occurrences
   - "Lister mes contacts" → énumérer les noms

   ✅ 'retrieval' = INFORMATION, FAITS, RÉSUMÉS (tout le reste)
   Exemples RETRIEVAL:
   - "Qui est Ayoub ?" → chercher des infos sur Ayoub
   - "Est-ce qu'Ayoub est marocain ?" → chercher des attributs personnels
   - "De quoi on a parlé avec X ?" → résumé du contenu
   - "Qu'est-ce qu'il a dit sur..." → recherche factuelle
   - "Résume mes échanges avec Y" → analyse sémantique

2. REFORMULATION:
   - Rends la question autonome (compréhensible sans historique)
   - Remplace les pronoms (il, ça, eux) par les noms réels de l'historique
   - Optimise pour la recherche sémantique

3. INTENTION:
   - 'specific_fact' = fait précis (date, lieu, nom, événement ponctuel)
   - 'broad_summary' = résumé, ambiance, thématiques, évolution
   - 'complex_reasoning' = croiser plusieurs infos, analyser en profondeur

4. DATES:
   - Si mentionnée: extrais plage [start, end] ISO YYYY-MM-DD
   - Sinon: null
   - "été dernier" = juin-août année précédente
   - "mois dernier" = calculer depuis aujourd'hui

RÉPONDS UNIQUEMENT EN JSON (ZÉRO texte autre):
{{
  "mode": "analytics|retrieval",
  "rewritten_query": "la question reformulée",
  "intent": "specific_fact|broad_summary|complex_reasoning",
  "date_range": {{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}}
}}"""

        user_content = f"HISTORIQUE :\n{formatted_history}\n\nDERNIÈRE QUESTION : {query}"

        try:
            logger.info(f"🔍 Analyzing query: '{query}'")
            logger.debug(f"Model: {self.model}")

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
            logger.debug(f"LLM raw response: {content}")
            data = json.loads(content)

            # Mapping des paramètres selon l'intention
            intent = data.get("intent", "complex_reasoning")
            params = self._get_params_for_intent(intent)
            mode = data.get("mode", "retrieval")

            date_range = data.get("date_range") or {}

            logger.info(f"✅ Analysis complete: mode={mode}, intent={intent}, top_k={params['top_k']}")
            logger.debug(f"  Rewritten query: '{data.get('rewritten_query', query)}'")
            logger.debug(f"  Date range: {date_range}")

            return AnalysisResult(
                rewritten_query=data.get("rewritten_query", query),
                intent=intent,
                mode=mode,
                top_k=params["top_k"],
                use_reranking=params["use_reranking"],
                expand_context=params["expand_context"],
                date_start=date_range.get("start"),
                date_end=date_range.get("end")
            )

        except Exception as e:
            logger.error(f"❌ Query Analysis Error: {e}", exc_info=True)
            logger.warning(f"⚠️ Falling back to default retrieval mode")
            # Fallback sur les valeurs par défaut
            return AnalysisResult(
                rewritten_query=query,
                intent="complex_reasoning",
                mode="retrieval",
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
