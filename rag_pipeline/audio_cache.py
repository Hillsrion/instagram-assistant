"""
Simple JSON-based cache for audio transcriptions.
"""
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Optional
from threading import Lock

from .config import default_config

logger = logging.getLogger(__name__)

class AudioCache:
    """
    Thread-safe cache for audio transcriptions.
    
    Structure:
    {
        "file_hash_or_path": {
            "transcript": "...",
            "model": "...",
            "timestamp": "..."
        }
    }
    """
    def __init__(self, cache_path: Path = None):
        self.cache_path = cache_path or default_config.audio_cache_path
        self.lock = Lock()
        self.cache: Dict[str, dict] = {}
        self._load()

    def _load(self):
        """Loads cache from disk."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                logger.info(f"Loaded {len(self.cache)} audio transcriptions from cache.")
            except Exception as e:
                logger.error(f"Failed to load audio cache: {e}")
                self.cache = {}
        else:
            self.cache = {}

    def save(self):
        """Saves cache to disk."""
        with self.lock:
            try:
                # atomic write
                temp_path = self.cache_path.with_suffix('.tmp')
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(self.cache, f, ensure_ascii=False, indent=2)
                temp_path.replace(self.cache_path)
            except Exception as e:
                logger.error(f"Failed to save audio cache: {e}")

    def get_file_hash(self, file_path: Path) -> str:
        """Calculates a quick hash of the file (size + modification time + name).
        
        Full content sha256 is safer but slower for large files.
        For now, let's use a robust 'quick hash'.
        """
        stat = file_path.stat()
        identifier = f"{file_path.name}_{stat.st_size}_{stat.st_mtime}"
        return hashlib.md5(identifier.encode()).hexdigest()

    def get(self, file_path: Path) -> Optional[str]:
        """Retrieves transcription if available."""
        file_hash = self.get_file_hash(file_path)
        entry = self.cache.get(file_hash)
        if entry:
            return entry.get('transcript')
        return None

    def set(self, file_path: Path, transcript: str, model: str = "unknown"):
        """Stores transcription."""
        file_hash = self.get_file_hash(file_path)
        with self.lock:
            self.cache[file_hash] = {
                "transcript": transcript,
                "model": model,
                "file_name": file_path.name,
                "original_path": str(file_path)
            }
