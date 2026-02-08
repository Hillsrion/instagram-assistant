"""
Date extractor module from user query.
Uses LLM to transform "last summer" into date range [start, end].
"""
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from rag_pipeline.core.config import Config

class QueryDateExtractor:
    """Extracts date ranges from natural language query."""
    
    def __init__(self, config: Config):
        self.config = config
        self.today = datetime.now()
        
    def extract_dates(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts a date range from a query.
        
        Returns:
            (start_date, end_date) in YYYY-MM-DD format or None
        """
        # System prompt optimized for date extraction (Ministral-friendly)
        # Kept in French/English mix as it parses French queries but logic is logic
        system_prompt = f"""Tu es un extracteur de dates (STRICT, concis).

Aujourd'hui: {self.today.strftime('%Y-%m-%d')}

TÂCHE:
1. Si AUCUNE date mentionnée → {{"has_date": false}}
2. Si date mentionnée → convertir en plage ISO YYYY-MM-DD

RÈGLES CLÉS:
- "été dernier" = juin-août année précédente
- "Noël" = 25 décembre année appropriée
- "mois dernier" = calculé depuis aujourd'hui
- RÉPONSE UNIQUEMENT: JSON, pas de texte supplémentaire

Format: {{"has_date": bool, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}}
"""

        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json={
                    "model": self.config.llm_model_fast,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Requête: {query}"}
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.0,  # Max determinism
                        "num_predict": 128
                    }
                },
                timeout=10.0  # Short timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                content = json.loads(result['message']['content'])
                
                if content.get("has_date"):
                    return (content.get("start_date"), content.get("end_date"))
            
        except Exception as e:
            print(f"⚠️ Date extraction error: {e}")
            
        return (None, None)