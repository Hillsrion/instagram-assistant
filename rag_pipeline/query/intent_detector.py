"""
Intent detector to optimize RAG parameters.
Uses LLM to classify user query.
"""
import requests
from enum import Enum
from typing import Dict, Any, Optional

from rag_pipeline.core.config import Config, default_config


class SearchIntent(str, Enum):
    """Search intent for retrieval optimization."""
    SPECIFIC_FACT = "specific_fact"      # Looking for precise info -> low top_k
    BROAD_SUMMARY = "broad_summary"      # Looking to understand broad topic -> high top_k
    COMPLEX_REASONING = "complex_reasoning" # Requires multiple viewpoints -> medium top_k


class IntentDetector:
    """Analyzes user intent to adapt RAG."""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
    
    def detect_intent(self, query: str) -> Dict[str, Any]:
        """
        Analyzes query and returns recommended parameters.
        """
        # Prompt kept in French/English mix as intent keywords are English in code but descriptions were French.
        # Translating descriptions to English for consistency.
        system_prompt = """You are an intent classifier (STRICT, ultra-concise).

CLASSIFY THE QUESTION INTO A CATEGORY:

1. 'specific_fact' = Precise fact (date, place, name, number)
2. 'broad_summary' = Summary/atmosphere/evolution of a broad topic
3. 'complex_reasoning' = Crossing multiple infos/viewpoints

MANDATORY ANSWER:
- ONE LINE ONLY
- CATEGORY NAME ONLY
- ZERO extra text"""

        try:
            # Direct call to Ollama
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
            
            # Parameter mapping
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
                    "use_reranking": False, # Too many docs for efficient/fast reranking
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
            # Silent fallback to default parameters
            return {
                "intent": None,
                "top_k": self.config.top_k,
                "use_reranking": True,
                "expand_context": True,
                "error": str(e)
            }