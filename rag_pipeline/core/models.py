"""
Data models for the RAG pipeline.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any

@dataclass
class Message:
    """An individual message."""
    timestamp: datetime
    author: str
    content: str
    has_media: bool = False
    media_type: Optional[str] = None  # photo, video, audio, link


@dataclass
class Chunk:
    """A conversation chunk with enriched metadata."""
    chunk_id: str
    conversation_id: str
    participants: List[str]
    date_start: str
    date_end: str
    message_count: int
    content: str
    file_source: str
    # New fields for "Gold Standard" RAG
    narrative_summary: Optional[str] = None
    reference_summary: Optional[str] = None  # Ground truth for overlap validation
    hypothetical_questions: Optional[List[str]] = None
    speaker_intents: Optional[Dict[str, str]] = None
    temporal_context: Optional[str] = None
    emotions: Optional[Dict[str, Any]] = None  # {dominant, tone, tension_level}
    entities: Optional[Dict[str, List[str]]] = None  # {locations: [], people: [], media: [], events: []}
    
    # New "Social" enrichment fields
    interaction_pattern: Optional[str] = None  # e.g. "Planification", "Récit", "Débat"
    initiative: Optional[str] = None  # e.g. "UserA leads", "Balanced"
    emotional_shift: Optional[str] = None  # e.g. "neutral -> happy"
    open_loops: Optional[List[str]] = None  # Unresolved topics
    
    # Generic metadata for auxiliary info (e.g. complexity scores)
    metadata: Optional[Dict[str, Any]] = None
    
    # Enrichment failure tracking
    enrichment_failed: bool = False
    enrichment_error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Chunk":
        # Filter out any unknown fields (e.g., 'summary' from old chunks)
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)