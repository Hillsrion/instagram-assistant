"Consolidated Query Analyzer (Omni-Prompt).\nMerges rewriting, intent detection, and date extraction into a single LLM call.\n"
import json
import requests
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from rag_pipeline.core.config import Config, default_config
from rag_pipeline.core.llm_provider import create_provider
from rag_pipeline.core.logger import get_logger
from rag_pipeline.enrichment.json_utils import repair_and_load_json
from rag_pipeline.core.prompts import QUERY_ANALYSIS_PROMPT
from rag_pipeline.core.schemas import QUERY_ANALYSIS_SCHEMA

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

    def __init__(self, config: Config = None, provider_type: str = "ollama"):
        self.config = config or default_config
        self.model = self.config.llm_model_fast
        self.provider = create_provider(self.config, self.model, provider_type)
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

        system_prompt = QUERY_ANALYSIS_PROMPT.format(
            today_str=today_str,
            iso_str=iso_str
        ) + "\nIMPORTANT: Do NOT use placeholders like 'XX' in dates. If a day or month is unknown, use '01' or provide a range covering the suspected period. If the year is unknown, omit the date range (set to null)."

        user_content = f"HISTORIQUE :\n{formatted_history}\n\nDERNIÈRE QUESTION : {query}"

        try:
            logger.info(f"🔍 Analyzing query: '{query}'")
            logger.debug(f"Model: {self.model}")

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]

            content = self.provider.generate(
                messages,
                temperature=0.0,
                max_tokens=256,
                format=QUERY_ANALYSIS_SCHEMA
            )
            logger.debug(f"LLM raw response: {content}")
            
            # Use robust repair and load utility
            data = repair_and_load_json(content)

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
            if date_start and ("-01-01" in date_start or "XX" in date_start.upper()):
                # Not a specific date, it's a fuzzy detection or placeholder → ignore
                logger.debug(f"  Ignoring vague or invalid date detection: {date_start}")
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
                "top_k": 15,  # Increased: 8→15 (+88% coverage) - dataset chunks are lighter than expected
                "use_reranking": True,
                "expand_context": False
            }
        elif intent == "broad_summary":
            return {
                "top_k": 40,  # Increased: 20→40 (+100% coverage) - real avg 375 tokens/chunk allows 2× more context
                "use_reranking": True,  # Enabled: quality over quantity
                "expand_context": True
            }
        else: # complex_reasoning or fallback
            return {
                "top_k": 30,  # Increased: 15→30 (+100% coverage) - balanced config based on 32k chunks analysis
                "use_reranking": True,
                "expand_context": True
            }