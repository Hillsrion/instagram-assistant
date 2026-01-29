"Consolidated Query Analyzer (Omni-Prompt).\nMerges rewriting, intent detection, and date extraction into a single LLM call.\n"
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
    """Consolidated analysis result of a query."""
    rewritten_query: str
    intent: str
    mode: str # 'retrieval' or 'analytics'
    top_k: int
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    use_reranking: bool = True
    expand_context: bool = True

class QueryAnalyzer:
    """Unified analyzer to reduce RAG pipeline latency."""

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.model = self.config.llm_model_fast
        self.today = datetime.now()

    def analyze(self, query: str, history: List[Dict[str, str]]) -> AnalysisResult:
        """
        Performs full query analysis in a single LLM call.
        """
        # Format recent history
        recent_history = history[-6:] if history else []
        formatted_history = ""
        for msg in recent_history:
            role = "Utilisateur" if msg['role'] == 'user' else "Assistant"
            formatted_history += f"{role}: {msg['content']}\n"

        today_str = self.today.strftime('%A %d %B %Y')
        iso_str = self.today.strftime('%Y-%m-%d')

        # Prompt kept in French mostly as it deals with French queries
        system_prompt = f"""Tu es un pré-processeur RAG (STRICT, JSON uniquement).
Aujourd'hui: {today_str} (ISO: {iso_str}).

Transforme la question en structure de recherche optimisée.

1. MODE (DÉCISION CRITIQUE):

   ✅ 'analytics' = COMPTAGE/STATISTIQUES/ENUMERATION UNIQUEMENT
   Exemples ANALYTICS:
   - "Combien j'ai de messages ?" → compter le total
   - "Nombre de messages avec Marie ?" → compter par contact
   - "Combien de fois on a parlé de sport ?" → compter des occurrences
   - "Lister mes contacts" → énumérer les noms
   - "Quels sont mes participants?" → énumérer

   ✅ 'retrieval' = INFORMATION, FAITS, RECHERCHES, RÉSUMÉS (tout le reste)
   Exemples RETRIEVAL:
   - "Qui est Ayoub ?" → chercher des infos sur Ayoub
   - "Est-ce qu'Ayoub est marocain ?" → chercher des attributs personnels
   - "J'ai déjà parlé d'un taxi ?" → RECHERCHE FACTUELLE (pas un comptage!)
   - "On a parlé de voiture ?" → VÉRIFICATION (pas un comptage!)
   - "De quoi on a parlé avec X ?" → résumé du contenu
   - "Qu'est-ce qu'il a dit sur..." → recherche sémantique
   - "Résume mes échanges avec Y" → analyse sémantique

   RÈGLE D'OR:
   - Si question = "Avons-nous parlé de X?" ou "Est-ce qu'on a mentionné Y?" → RETRIEVAL
   - Ne confonds pas avec "Combien de fois?" qui est ANALYTICS

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
  "date_range": {{"{'start'}": "YYYY-MM-DD", "{'end'}": "YYYY-MM-DD"}}
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

            # Map parameters based on intent
            intent = data.get("intent", "complex_reasoning")
            params = self._get_params_for_intent(intent)
            mode = data.get("mode", "retrieval")

            date_range = data.get("date_range") or {}
            date_start = date_range.get("start")
            date_end = date_range.get("end")

            # Validation: ignore vague or auto-detected dates if suspicious
            # (If query doesn't mention specific period, do not filter)
            # Simple detection: if date_start = "YYYY-01-01" it's likely "since beginning of year"
            if date_start and "-01-01" in date_start:
                # Not a specific date, it's a fuzzy detection → ignore
                logger.debug(f"  Ignoring vague date detection: {date_start}")
                date_start = None
                date_end = None

            logger.info(f"✅ Analysis complete: mode={mode}, intent={intent}, top_k={params['top_k']}")
            logger.debug(f"  Rewritten query: '{data.get('rewritten_query', query)}'")
            logger.debug(f"  Date range: {date_start} → {date_end}")

            return AnalysisResult(
                rewritten_query=data.get("rewritten_query", query),
                intent=intent,
                mode=mode,
                top_k=params["top_k"],
                use_reranking=params["use_reranking"],
                expand_context=params["expand_context"],
                date_start=date_start,
                date_end=date_end
            )

        except Exception as e:
            logger.error(f"❌ Query Analysis Error: {e}", exc_info=True)
            logger.warning(f"⚠️ Falling back to default retrieval mode")
            # Fallback to default values
            return AnalysisResult(
                rewritten_query=query,
                intent="complex_reasoning",
                mode="retrieval",
                top_k=self.config.top_k
            )

    def _get_params_for_intent(self, intent: str) -> Dict[str, Any]:
        """Returns optimized search parameters for an intent."""
        if intent == "specific_fact":
            return {
                "top_k": 5,
                "use_reranking": True,
                "expand_context": False
            }
        elif intent == "broad_summary":
            return {
                "top_k": 15,
                "use_reranking": False, # Too many docs, prioritize mass
                "expand_context": True
            }
        else: # complex_reasoning or fallback
            return {
                "top_k": 10,
                "use_reranking": True,
                "expand_context": True
            }