"""
Système de logging structuré pour déboguer le pipeline RAG.
Enregistre chaque étape de traitement d'une requête.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Créer le répertoire de logs s'il n'existe pas
LOG_DIR = Path("rag_data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Fichier de log principal
LOG_FILE = LOG_DIR / "rag_pipeline.log"
DEBUG_LOG_FILE = LOG_DIR / "debug.jsonl"

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)-8s %(name)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("rag_pipeline")


class RequestLogger:
    """Logger structuré pour tracer une requête spécifique."""

    def __init__(self, query: str, request_id: Optional[str] = None):
        self.query = query
        self.request_id = request_id or datetime.now().isoformat()
        self.events = []
        self.start_time = datetime.now()

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Enregistre un événement dans la trace de requête."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data
        }
        self.events.append(event)

        # Log aussi en sortie console
        logger.debug(f"[{self.request_id}] {event_type}: {json.dumps(data, ensure_ascii=False)}")

    def log_analysis(self, analysis_result: Dict[str, Any]):
        """Enregistre le résultat de l'analyse de requête."""
        self.log_event("query_analysis", {
            "query": self.query,
            "mode": analysis_result.get("mode"),
            "intent": analysis_result.get("intent"),
            "rewritten_query": analysis_result.get("rewritten_query"),
            "date_start": analysis_result.get("date_start"),
            "date_end": analysis_result.get("date_end"),
            "top_k": analysis_result.get("top_k"),
        })

    def log_retrieval(self, source_count: int, top_scores: list):
        """Enregistre le résultat de la recherche."""
        self.log_event("retrieval", {
            "source_count": source_count,
            "top_scores": top_scores[:5] if top_scores else []
        })

    def log_llm_call(self, model: str, response_length: int):
        """Enregistre l'appel LLM."""
        self.log_event("llm_response", {
            "model": model,
            "response_length": response_length
        })

    def log_error(self, error_type: str, error_message: str, traceback: Optional[str] = None):
        """Enregistre une erreur."""
        self.log_event("error", {
            "type": error_type,
            "message": error_message,
            "traceback": traceback
        })

    def save(self):
        """Sauvegarde la trace complète dans un fichier JSONL."""
        duration = (datetime.now() - self.start_time).total_seconds()

        record = {
            "request_id": self.request_id,
            "query": self.query,
            "duration_seconds": duration,
            "event_count": len(self.events),
            "events": self.events
        }

        with open(DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

        logger.info(f"Request trace saved: {self.request_id} (duration: {duration:.2f}s)")


def get_logger():
    """Retourne le logger principal."""
    return logger
