"""
Chunk complexity analyzer for intelligent model routing.

Scores chunks on 6 dimensions to determine if they should be processed
with a fast 3B model or a quality 8B model.
"""
import re
import math
from dataclasses import dataclass
from typing import Dict, Any, Optional
from rag_pipeline.core.models import Chunk


@dataclass
class ComplexityMetrics:
    """Individual complexity metric scores."""
    participants: float
    information_content: float  # Replaces density + lexical_diversity
    media: float
    size: float
    dialogue: float


@dataclass
class ComplexityAnalysis:
    """Complete complexity analysis result."""
    score: float  # 0.0-1.0
    category: str  # "simple", "medium", "complex"
    metrics: ComplexityMetrics
    breakdown: Dict[str, float]  # For debugging


class ChunkComplexityAnalyzer:
    """
    Analyzes chunk complexity using 5 weighted metrics to determine
    which LLM model should process it (3B for simple, 8B for complex).

    Metrics:
    - Information Content (0.40): Volume of unique concepts (Unique Words). Replaces Density/Lexical.
    - Participants (0.20): More people = more perspectives.
    - Size (0.20): Number of messages.
    - Dialogue (0.15): Emotions/questions = nuanced sentiment.
    - Media (0.05): Links/media = need context.
    """

    def __init__(self, config=None):
        self.config = config

        # Thresholds for classification
        self.simple_threshold = 0.25
        self.complex_threshold = 0.40

        # Metric weights (must sum to 1.0)
        self.weights = {
            "information_content": 0.40,
            "participants": 0.20,
            "size": 0.20,
            "dialogue": 0.15,
            "media": 0.05,
        }

        # Load from config if available
        if config:
            self.simple_threshold = getattr(config, 'complexity_simple_threshold', 0.25)
            self.complex_threshold = getattr(config, 'complexity_complex_threshold', 0.40)
            if hasattr(config, 'complexity_weights') and config.complexity_weights:
                self.weights = config.complexity_weights

    def analyze(self, chunk: Chunk) -> ComplexityAnalysis:
        """
        Analyze chunk complexity and return score + category.

        Args:
            chunk: Chunk to analyze

        Returns:
            ComplexityAnalysis with score (0.0-1.0) and category
        """
        metrics = self._compute_metrics(chunk)
        score = self._calculate_score(metrics)
        category = self._classify(score)

        breakdown = {
            "information_content": metrics.information_content,
            "participants": metrics.participants,
            "size": metrics.size,
            "dialogue": metrics.dialogue,
            "media": metrics.media,
        }

        return ComplexityAnalysis(
            score=score,
            category=category,
            metrics=metrics,
            breakdown=breakdown
        )

    def _compute_metrics(self, chunk: Chunk) -> ComplexityMetrics:
        """Compute all complexity metrics."""
        # 0. Preparation: Get cleaned content and active participants
        clean_content = self._get_clean_content(chunk.content or "")
        active_participants = self._get_active_authors(chunk.content or "")

        return ComplexityMetrics(
            participants=self._score_participants(active_participants),
            information_content=self._score_information_content(clean_content),
            media=self._score_media(clean_content, chunk.message_count),
            size=self._score_size(chunk.message_count),
            dialogue=self._score_dialogue(clean_content, chunk.message_count),
        )

    def _get_clean_content(self, content: str) -> str:
        """Remove structural noise like reaction lines and normalize URLs."""
        lines = []
        for line in content.split('\n'):
            # Remove reaction lines
            if "💬 Réactions:" in line or "❤️ Réactions:" in line:
                continue
            
            # Extract actual message content to ignore headers/timestamps in density
            # Format: [2024-...] Author: Message
            header_match = re.search(r'\] .*?: (.*)', line)
            if header_match:
                msg = header_match.group(1)
            else:
                msg = line
            
            # Normalize URLs: replace long links with a short token
            # This prevents URLs from inflating density and lexical diversity scores
            msg = re.sub(r'http[s]?://\S+', '[URL]', msg)
            lines.append(msg)
            
        return "\n".join(lines)


    def _get_active_authors(self, content: str) -> list:
        """Extract unique authors who actually sent messages in this chunk."""
        # Regex to find authors between timestamp bracket and colon
        # Format: [2024-01-01 12:00] Author Name: Message
        authors = re.findall(r'\] (.*?):', content)
        return list(set(authors))

    def _score_participants(self, active_participants: list) -> float:
        """
        Score based on number of ACTIVE participants.
        Monologue (<2): 0.0
        Dialogue (2): 0.3   (Standard conversation baseline)
        Small Group (3): 0.6
        Group (4+): 1.0
        """
        count = len(active_participants)
        if count < 2:
            return 0.0
        elif count == 2:
            return 0.3  # Give baseline score to DMs so they aren't artificially "simple"
        elif count == 3:
            return 0.6
        else:
            return 1.0

    def _score_information_content(self, clean_content: str) -> float:
        """
        Score based on the volume of unique concepts (Unique Words).
        Combines the previous 'Density' and 'Lexical Diversity' metrics into one robust signal.
        
        < 30 unique words: Simple/Phatic (0.0)
        > 150 unique words: Dense/Rich (1.0)
        """
        words = re.findall(r'\b\w+\b', clean_content.lower())
        unique_count = len(set(words))
        
        if unique_count < 30:
            return 0.0
        elif unique_count < 150:
            return (unique_count - 30) / 120.0
        else:
            return 1.0

    def _score_media(self, clean_content: str, message_count: int) -> float:
        """Score based on media/link ratio."""
        msg_count = max(message_count or 1, 1)
        media_count = self._count_media_and_links(clean_content)
        media_ratio = media_count / msg_count

        if media_ratio < 0.10:
            return 0.0
        elif media_ratio < 0.30:
            return (media_ratio - 0.10) / 0.20
        else:
            return 1.0

    def _score_size(self, message_count: int) -> float:
        """Score based on message count."""
        count = message_count or 0
        if count < 15:
            return 0.0
        elif count < 35:
            return (count - 15) / 20.0
        else:
            return 1.0

    def _score_dialogue(self, clean_content: str, message_count: int) -> float:
        """Score based on dialogue patterns in cleaned content."""
        msg_count = max(message_count or 1, 1)
        questions = len(re.findall(r'\?', clean_content))
        exclamations = len(re.findall(r'!', clean_content))
        emojis = len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF]', clean_content))

        ratio = (questions + exclamations + emojis) / msg_count
        if ratio < 0.2:
            return 0.0
        elif ratio < 0.5:
            return (ratio - 0.2) / 0.3
        else:
            return 1.0

    def _calculate_score(self, metrics: ComplexityMetrics) -> float:
        """Calculate weighted complexity score (0.0-1.0)."""
        score = (
            metrics.information_content * self.weights["information_content"] +
            metrics.participants * self.weights["participants"] +
            metrics.size * self.weights["size"] +
            metrics.dialogue * self.weights["dialogue"] +
            metrics.media * self.weights["media"]
        )
        return max(0.0, min(1.0, score))

    def _classify(self, score: float) -> str:
        """Classify score into category."""
        if score < self.simple_threshold:
            return "simple"
        elif score < self.complex_threshold:
            return "medium"
        else:
            return "complex"

    @staticmethod
    def _count_media_and_links(text: str) -> int:
        """Count mentions of media files and URLs strictly."""
        urls = len(re.findall(r'http[s]?://\S+|www\.\S+', text))
        # Stricter file pattern to avoid usernames with dots
        files = len(re.findall(r'(?:^|\s)[\w\-]+\.(?:jpg|jpeg|png|gif|mp4|mov|pdf|heic)\b', text, re.IGNORECASE))
        # Indicators added by chunker
        indicators = len(re.findall(r'\[(Photo|Vidéo|Audio)\]', text))
        
        keywords = len(re.findall(r'\b(photo|image|vidéo|video|fichier|file|lien|link)\b', text, re.IGNORECASE))
        return urls + files + indicators + keywords
