"""
Module d'extraction de dates depuis une requête utilisateur.
Utilise le LLM pour transformer "été dernier" en plage de dates [start, end].
"""
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from .config import Config

class QueryDateExtractor:
    """Extrait des plages de dates d'une requête en langage naturel."""
    
    def __init__(self, config: Config):
        self.config = config
        self.today = datetime.now()
        
    def extract_dates(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrait une plage de dates d'une requête.
        
        Returns:
            (start_date, end_date) au format YYYY-MM-DD ou None
        """
        # Prompt système optimisé pour l'extraction de dates
        system_prompt = f"""
        Tu es un expert en extraction temporelle.
        Aujourd'hui nous sommes le : {self.today.strftime('%A %d %B %Y')} (ISO: {self.today.strftime('%Y-%m-%d')}).
        
        Ta mission : Identifier si la requête de l'utilisateur contient une référence temporelle explicite ou implicite.
        
        Règles :
        1. Si aucune date n'est mentionnée, retourne JSON : {{"has_date": false}}
        2. Si une date est mentionnée, convertis-la en plage [start_date, end_date] au format ISO YYYY-MM-DD.
        3. Pour "été dernier" (si on est en 2026), c'est l'été 2025 (01 juin au 31 aout).
        4. Pour "Noël", c'est le 25 décembre de l'année pertinente.
        5. Pour "le mois dernier", calcule par rapport à la date d'aujourd'hui.
        
        Exemple Output :
        {{"has_date": true, "start_date": "2024-06-01", "end_date": "2024-08-31"}}
        """

        try:
            response = requests.post(
                f"{self.config.ollama_url}/api/chat",
                json={
                    "model": self.config.llm_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Requête: {query}"}
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.0,  # Déterminisme maximal
                        "num_predict": 128
                    }
                },
                timeout=10.0  # Timeout court pour ne pas ralentir la recherche
            )
            
            if response.status_code == 200:
                result = response.json()
                content = json.loads(result['message']['content'])
                
                if content.get("has_date"):
                    return (content.get("start_date"), content.get("end_date"))
            
        except Exception as e:
            print(f"⚠️ Erreur extraction date: {e}")
            
        return (None, None)
