"""
Structured logging system to debug the RAG pipeline.
Records each step of request processing.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Create logs directory if it doesn't exist
LOG_DIR = Path("rag_data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Main log file
LOG_FILE = LOG_DIR / "rag_pipeline.log"
DEBUG_LOG_FILE = LOG_DIR / "debug.jsonl"

# Global logger - will be configured by initialize_logging()
logger = logging.getLogger("rag_pipeline")
logger.setLevel(logging.DEBUG)
_logging_initialized = False


def initialize_logging(verbose: bool = False):
    """
    Initializes the logging system.

    Args:
        verbose: If True, logs to console AND files.
                If False, logs nothing to console.
    """
    global _logging_initialized

    if _logging_initialized:
        return

    # Clear existing handlers
    logger.handlers.clear()

    if verbose:
        # Verbose mode: console AND files
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-8s %(name)s - %(message)s'
        )

        # File handler
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console handler
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    else:
        # Silent mode: NullHandler
        logger.addHandler(logging.NullHandler())

    _logging_initialized = True


class RequestLogger:
    """Structured logger to trace a specific request."""

    def __init__(self, query: str, request_id: Optional[str] = None):
        self.query = query
        self.request_id = request_id or datetime.now().isoformat()
        self.events = []
        self.start_time = datetime.now()

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Records an event in the request trace."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data
        }
        self.events.append(event)

        # Log to console output as well
        logger.debug(f"[{self.request_id}] {event_type}: {json.dumps(data, ensure_ascii=False)}")

    def log_analysis(self, analysis_result: Dict[str, Any]):
        """Records the query analysis result."""
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
        """Records the retrieval result."""
        self.log_event("retrieval", {
            "source_count": source_count,
            "top_scores": top_scores[:5] if top_scores else []
        })

    def log_llm_call(self, model: str, response_length: int):
        """Records the LLM call."""
        self.log_event("llm_response", {
            "model": model,
            "response_length": response_length
        })

    def log_error(self, error_type: str, error_message: str, traceback: Optional[str] = None):
        """Records an error."""
        self.log_event("error", {
            "type": error_type,
            "message": error_message,
            "traceback": traceback
        })

    def save(self):
        """Saves the complete trace to a JSONL file."""
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
    """Returns the main logger."""
    return logger