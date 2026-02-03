"""
Chunk complexity analyzer for intelligent model routing.

Scores chunks on 6 dimensions to determine if they should be processed
with a fast 3B model or a quality 8B model.
"""
import re
import math
from dataclasses import dataclass
from typing import Dict, Any, Optional
from .chunker import Chunk


@dataclass
class ComplexityMetrics:
    """Individual complexity metric scores."""
    participants: float
    density: float
    media: float
    size: float
    lexical_diversity: float
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
    Analyzes chunk complexity using 6 weighted metrics to determine
    which LLM model should process it (3B for simple, 8B for complex).

    Metrics:
    - Participants (0.20): More people = more perspectives
    - Density (0.25): Longer messages = more content to analyze
    - Media (0.15): Links/media = need context
    - Size (0.15): More messages = more synthesis needed
    - Lexical Diversity (0.15): Rich vocabulary = subtle meaning
    - Dialogue Patterns (0.10): Emotions/questions = nuanced sentiment
    """

    def __init__(self, config=None):
        self.config = config

        # Thresholds for classification
        self.simple_threshold = 0.35
        self.complex_threshold = 0.65

        # Metric weights (must sum to 1.0)
        self.weights = {
            "participants": 0.20,
            "density": 0.30,      # Increased from 0.25
            "media": 0.05,        # Decreased from 0.15
            "size": 0.25,         # Increased from 0.15
            "lexical_diversity": 0.15, # Decreased from 0.15 to keep sum at 1.0
            "dialogue": 0.05,     # Decreased from 0.10
        }

        # Load from config if available
        if config:
            self.simple_threshold = getattr(config, 'complexity_simple_threshold', 0.35)
            self.complex_threshold = getattr(config, 'complexity_complex_threshold', 0.65)
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
            "participants": metrics.participants,
            "density": metrics.density,
            "media": metrics.media,
            "size": metrics.size,
            "lexical_diversity": metrics.lexical_diversity,
            "dialogue": metrics.dialogue,
        }

        return ComplexityAnalysis(
            score=score,
            category=category,
            metrics=metrics,
            breakdown=breakdown
        )

    def _compute_metrics(self, chunk: Chunk) -> ComplexityMetrics:
        """Compute all 6 complexity metrics."""
        return ComplexityMetrics(
            participants=self._score_participants(chunk),
            density=self._score_density(chunk),
            media=self._score_media(chunk),
            size=self._score_size(chunk),
            lexical_diversity=self._score_lexical_diversity(chunk),
            dialogue=self._score_dialogue(chunk),
        )

    def _score_participants(self, chunk: Chunk) -> float:
        """
        Score based on number of participants.

        1-2: 0.0 (simple dyadic)
        3-4: 0.5 (small group)
        5+: 1.0 (complex group dynamic)
        """
        participant_count = len(chunk.participants) if chunk.participants else 0

        if participant_count <= 2:
            return 0.0
        elif participant_count <= 4:
            return 0.5
        else:
            return 1.0

    def _score_density(self, chunk: Chunk) -> float:
        """
        Score based on information density (tokens per message).

        <50: 0.0 (sparse)
        50-100: 0.5 (moderate)
        >100: 1.0 (dense)
        """
        content = chunk.content or ""
        message_count = chunk.message_count or 1

        total_tokens = self._estimate_tokens(content)
        tokens_per_msg = total_tokens / max(message_count, 1)

        if tokens_per_msg < 50:
            return 0.0
        elif tokens_per_msg < 100:
            return (tokens_per_msg - 50) / 50.0
        else:
            return 1.0

    def _score_media(self, chunk: Chunk) -> float:
        """
        Score based on media/link ratio.

        0-10%: 0.0
        10-30%: 0.5
        >30%: 1.0
        """
        content = chunk.content or ""
        message_count = max(chunk.message_count or 1, 1)

        media_count = self._count_media_and_links(content)
        media_ratio = media_count / message_count if message_count > 0 else 0

        if media_ratio < 0.10:
            return 0.0
        elif media_ratio < 0.30:
            return (media_ratio - 0.10) / 0.20
        else:
            return 1.0

    def _score_size(self, chunk: Chunk) -> float:
        """
        Score based on chunk size (message count).

        <15: 0.0
        15-35: 0.5
        >35: 1.0
        """
        message_count = chunk.message_count or 0

        if message_count < 15:
            return 0.0
        elif message_count < 35:
            return (message_count - 15) / 20.0
        else:
            return 1.0

    def _score_lexical_diversity(self, chunk: Chunk) -> float:
        """
        Score based on lexical diversity (normalized by text length).

        Uses formula: unique_words / sqrt(total_words)
        This avoids bias towards short texts.

        <0.5: 0.0 (repetitive)
        0.5-0.8: 0.5 (moderate)
        >0.8: 1.0 (rich vocabulary)
        """
        content = chunk.content or ""
        diversity = self._compute_lexical_diversity(content)

        if diversity < 0.5:
            return 0.0
        elif diversity < 0.8:
            return (diversity - 0.5) / 0.3
        else:
            return 1.0

    def _score_dialogue(self, chunk: Chunk) -> float:
        """
        Score based on dialogue patterns (questions, exclamations, emojis).

        Ratio per message:
        <0.2: 0.0
        0.2-0.5: 0.5
        >0.5: 1.0
        """
        content = chunk.content or ""
        message_count = max(chunk.message_count or 1, 1)

        # Count dialogue markers
        questions = len(re.findall(r'\?', content))
        exclamations = len(re.findall(r'!', content))
        # Simple emoji detection
        emojis = len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF]', content))

        dialogue_count = questions + exclamations + emojis
        ratio = dialogue_count / message_count if message_count > 0 else 0

        if ratio < 0.2:
            return 0.0
        elif ratio < 0.5:
            return (ratio - 0.2) / 0.3
        else:
            return 1.0

    def _calculate_score(self, metrics: ComplexityMetrics) -> float:
        """Calculate weighted complexity score (0.0-1.0)."""
        score = (
            metrics.participants * self.weights["participants"] +
            metrics.density * self.weights["density"] +
            metrics.media * self.weights["media"] +
            metrics.size * self.weights["size"] +
            metrics.lexical_diversity * self.weights["lexical_diversity"] +
            metrics.dialogue * self.weights["dialogue"]
        )

        # Clamp to [0.0, 1.0]
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
    def _estimate_tokens(text: str) -> int:
        """Rough token count estimate (1 token ≈ 4 characters)."""
        return max(len(text) // 4, 1)

    @staticmethod
    def _count_media_and_links(text: str) -> int:
        """Count mentions of media files and URLs/links."""
        # Count URL patterns
        urls = len(re.findall(r'http[s]?://\S+|www\.\S+', text))
        # Count file patterns (.jpg, .mp4, .pdf, etc.)
        files = len(re.findall(r'\.\w{2,4}\b', text))
        # Count media keywords
        media_keywords = re.findall(
            r'\b(photo|image|vidéo|video|fichier|file|lien|link|mp4|jpg|png|pdf|document)\b',
            text,
            re.IGNORECASE
        )
        return urls + files + len(media_keywords)

    @staticmethod
    def _compute_lexical_diversity(text: str) -> float:
        """
        Compute normalized lexical diversity.

        Formula: unique_words / sqrt(total_words)
        This avoids bias where short texts have artificially high ratios.
        """
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return 0.0

        total_words = len(words)
        unique_words = len(set(words))

        if total_words < 2:
            return 0.0

        # Normalized metric
        diversity = unique_words / math.sqrt(total_words)
        return min(diversity, 1.0)  # Cap at 1.0
