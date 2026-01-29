"""
Data models for hierarchical summaries.
Allows answering "big picture" queries like:
- "What did we talk about with Marie this summer?"
- "Summarize my conversations with Paul"
"""
from dataclasses import dataclass, asdict, field
from typing import List, Optional


@dataclass
class ConversationSummary:
    """Global summary of an entire conversation."""
    summary_id: str                    # "{conversation_id}_summary"
    conversation_id: str
    participants: List[str]
    date_start: str                    # First date of conversation (ISO)
    date_end: str                      # Last date (ISO)
    total_messages: int
    total_chunks: int

    # LLM-generated fields
    summary: str                       # Narrative summary (2-3 sentences)
    main_topics: List[str]             # 3-5 main topics
    relationship_dynamic: str          # Relationship type/dynamic
    notable_events: List[str]          # Notable events

    chunk_ids: List[str]               # Linked chunks

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationSummary":
        return cls(**data)

    def get_embedding_text(self) -> str:
        """Returns text to encode for vector search."""
        parts = []

        # Participants
        parts.append(f"Conversation with {', '.join(self.participants)}")

        # Period
        parts.append(f"Period: {self.date_start[:10]} to {self.date_end[:10]}")

        # Summary
        parts.append(f"Summary: {self.summary}")

        # Topics
        if self.main_topics:
            parts.append(f"Main topics: {', '.join(self.main_topics)}")

        # Relationship dynamic
        if self.relationship_dynamic:
            parts.append(f"Relationship type: {self.relationship_dynamic}")

        # Events
        if self.notable_events:
            parts.append(f"Notable events: {', '.join(self.notable_events)}")

        return "\n".join(parts)


@dataclass
class PeriodSummary:
    """Summary of a period (month) for a conversation."""
    summary_id: str                    # "{conversation_id}_period_{YYYY-MM}"
    conversation_id: str
    participants: List[str]
    period: str                        # "2024-06" (YYYY-MM format)
    date_start: str
    date_end: str
    message_count: int

    # LLM-generated fields
    summary: str                       # Period summary
    topics: List[str]                  # Topics during period
    mood: str                          # General mood

    chunk_ids: List[str]               # Chunks in this period

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PeriodSummary":
        return cls(**data)

    def get_embedding_text(self) -> str:
        """Returns text to encode for vector search."""
        parts = []

        # Participants and period
        parts.append(f"Conversation with {', '.join(self.participants)} in {self.period}")

        # Precise period
        parts.append(f"From {self.date_start[:10]} to {self.date_end[:10]}")

        # Summary
        parts.append(f"Summary: {self.summary}")

        # Topics
        if self.topics:
            parts.append(f"Topics discussed: {', '.join(self.topics)}")

        # Mood
        if self.mood:
            parts.append(f"Mood: {self.mood}")

        return "\n".join(parts)