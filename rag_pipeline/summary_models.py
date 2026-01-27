"""
Modèles de données pour les résumés hiérarchiques.
Permet de répondre aux requêtes "big picture" comme :
- "De quoi a-t-on parlé avec Marie cet été ?"
- "Résume mes conversations avec Paul"
"""
from dataclasses import dataclass, asdict, field
from typing import List, Optional


@dataclass
class ConversationSummary:
    """Résumé global d'une conversation entière."""
    summary_id: str                    # "{conversation_id}_summary"
    conversation_id: str
    participants: List[str]
    date_start: str                    # Première date de la conversation (ISO)
    date_end: str                      # Dernière date (ISO)
    total_messages: int
    total_chunks: int

    # LLM-generated fields
    summary: str                       # Résumé narratif (2-3 phrases)
    main_topics: List[str]             # 3-5 sujets principaux
    relationship_dynamic: str          # Type de relation/dynamique
    notable_events: List[str]          # Événements marquants

    chunk_ids: List[str]               # Chunks liés

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationSummary":
        return cls(**data)

    def get_embedding_text(self) -> str:
        """Retourne le texte à encoder pour la recherche vectorielle."""
        parts = []

        # Participants
        parts.append(f"Conversation avec {', '.join(self.participants)}")

        # Période
        parts.append(f"Période: {self.date_start[:10]} à {self.date_end[:10]}")

        # Résumé principal
        parts.append(f"Résumé: {self.summary}")

        # Sujets
        if self.main_topics:
            parts.append(f"Sujets principaux: {', '.join(self.main_topics)}")

        # Dynamique relationnelle
        if self.relationship_dynamic:
            parts.append(f"Type de relation: {self.relationship_dynamic}")

        # Événements
        if self.notable_events:
            parts.append(f"Événements marquants: {', '.join(self.notable_events)}")

        return "\n".join(parts)


@dataclass
class PeriodSummary:
    """Résumé d'une période (mois) pour une conversation."""
    summary_id: str                    # "{conversation_id}_period_{YYYY-MM}"
    conversation_id: str
    participants: List[str]
    period: str                        # "2024-06" (format YYYY-MM)
    date_start: str
    date_end: str
    message_count: int

    # LLM-generated fields
    summary: str                       # Résumé de la période
    topics: List[str]                  # Sujets de la période
    mood: str                          # Ambiance générale

    chunk_ids: List[str]               # Chunks de cette période

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PeriodSummary":
        return cls(**data)

    def get_embedding_text(self) -> str:
        """Retourne le texte à encoder pour la recherche vectorielle."""
        parts = []

        # Participants et période
        parts.append(f"Conversation avec {', '.join(self.participants)} en {self.period}")

        # Période précise
        parts.append(f"Du {self.date_start[:10]} au {self.date_end[:10]}")

        # Résumé
        parts.append(f"Résumé: {self.summary}")

        # Sujets
        if self.topics:
            parts.append(f"Sujets abordés: {', '.join(self.topics)}")

        # Ambiance
        if self.mood:
            parts.append(f"Ambiance: {self.mood}")

        return "\n".join(parts)
