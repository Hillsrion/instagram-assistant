"""
Cross-Encoder Reranker to improve retrieval accuracy.
Uses BGE-reranker to reorder candidates after dense retrieval.
"""
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass

from .config import Config, default_config
from .chunker import Chunk


@dataclass
class RerankResult:
    """Result after reranking."""
    chunk: Chunk
    dense_score: float
    rerank_score: float
    final_rank: int


class CrossEncoderReranker:
    """
    Reranker based on a cross-encoder.

    The cross-encoder takes (query, document) as input and produces
    a relevance score more accurate than cosine similarity.
    """

    def __init__(self, config: Config = None, model_name: str = None):
        self.config = config or default_config
        self.model_name = model_name or "BAAI/bge-reranker-base"
        self.model = None
        self._device = None

    def _load_model(self):
        """Loads the cross-encoder model (lazy loading)."""
        if self.model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder
            import torch
        except ImportError:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            )

        # Determine device
        if self.config.use_gpu and torch.cuda.is_available():
            self._device = "cuda"
        elif self.config.use_gpu and torch.backends.mps.is_available():
            self._device = "mps"
        else:
            self._device = "cpu"

        print(f"📦 Loading reranker {self.model_name}...")
        print(f"🖥️  Device: {self._device}")

        self.model = CrossEncoder(
            self.model_name,
            device=self._device,
            max_length=512  # Limit to avoid OOM
        )

        print("✅ Reranker loaded")

    def rerank(
        self,
        query: str,
        candidates: List[Tuple[Chunk, float]],  # (chunk, dense_score)
        top_k: int = 5
    ) -> List[RerankResult]:
        """
        Reranks candidates using the cross-encoder.

        Args:
            query: User question
            candidates: List of (chunk, dense_score) sorted by dense_score
            top_k: Number of results to return

        Returns:
            List of RerankResult sorted by rerank_score
        """
        if not candidates:
            return []

        self._load_model()

        # Prepare (query, document) pairs
        pairs = []
        for chunk, _ in candidates:
            # Optimal construction for Cross-Encoder
            text_parts = []
            
            # 1. Hypothetical questions (Very strong signal if match)
            if chunk.hypothetical_questions:
                # Concatenate questions so reranker sees similarity
                text_parts.append("Questions covered: " + " ".join(chunk.hypothetical_questions))
            
            # 2. Temporal context (Temporal signal)
            if chunk.temporal_context:
                text_parts.append(f"Period: {chunk.temporal_context}")

            # 3. Participant intents
            if chunk.speaker_intents:
                intents_str = ", ".join(f"{p}: {i}" for p, i in chunk.speaker_intents.items())
                text_parts.append(f"Intents: {intents_str}")

            # 4. Emotions (Emotional context)
            if chunk.emotions:
                emotion_parts = []
                if chunk.emotions.get("dominant"):
                    emotion_parts.append(chunk.emotions["dominant"])
                if chunk.emotions.get("tone"):
                    emotion_parts.append(f"tone {chunk.emotions['tone']}")
                if chunk.emotions.get("tension_level"):
                    emotion_parts.append(f"tension {chunk.emotions['tension_level']}")
                if emotion_parts:
                    text_parts.append(f"Mood: {', '.join(emotion_parts)}")

            # 5. Narrative Summary (Strong context)
            if chunk.narrative_summary:
                text_parts.append(f"Summary: {chunk.narrative_summary}")

            # 6. Content (Evidence)
            # Keep significant excerpt (900 chars) to balance new fields
            text_parts.append(chunk.content[:900])
            
            doc_text = "\n".join(text_parts)
            pairs.append([query, doc_text])

        # Get scores from cross-encoder
        rerank_scores = self.model.predict(pairs, show_progress_bar=False)

        # Combine with dense scores and sort
        results = []
        for i, ((chunk, dense_score), rerank_score) in enumerate(zip(candidates, rerank_scores)):
            results.append(RerankResult(
                chunk=chunk,
                dense_score=dense_score,
                rerank_score=float(rerank_score),
                final_rank=0  # Will be updated after sort
            ))

        # Sort by rerank_score
        results.sort(key=lambda x: x.rerank_score, reverse=True)

        # Update ranks and limit
        for i, result in enumerate(results[:top_k]):
            result.final_rank = i + 1

        return results[:top_k]

    def rerank_with_fusion(
        self,
        query: str,
        candidates: List[Tuple[Chunk, float]],
        top_k: int = 5,
        alpha: float = 0.3  # Weight of dense score (1-alpha = rerank weight)
    ) -> List[RerankResult]:
        """
        Rerank with score fusion (dense + rerank).

        Formula: final_score = alpha * dense_score + (1-alpha) * rerank_score
        """
        if not candidates:
            return []

        self._load_model()

        pairs = []
        for chunk, _ in candidates:
            summary = chunk.narrative_summary if chunk.narrative_summary else chunk.summary
            doc_text = f"{summary}\n\n{chunk.content[:1500]}"
            pairs.append([query, doc_text])

        rerank_scores = self.model.predict(pairs, show_progress_bar=False)

        # Normalize scores for fusion
        dense_scores = np.array([score for _, score in candidates])
        rerank_scores = np.array(rerank_scores)

        # Min-max normalization
        if dense_scores.max() != dense_scores.min():
            dense_norm = (dense_scores - dense_scores.min()) / (dense_scores.max() - dense_scores.min())
        else:
            dense_norm = np.ones_like(dense_scores)

        if rerank_scores.max() != rerank_scores.min():
            rerank_norm = (rerank_scores - rerank_scores.min()) / (rerank_scores.max() - rerank_scores.min())
        else:
            rerank_norm = np.ones_like(rerank_scores)

        # Fusion
        final_scores = alpha * dense_norm + (1 - alpha) * rerank_norm

        # Create results
        results = []
        for i, ((chunk, dense_score), rerank_score, final_score) in enumerate(
            zip(candidates, rerank_scores, final_scores)
        ):
            results.append(RerankResult(
                chunk=chunk,
                dense_score=dense_score,
                rerank_score=float(final_score),  # Storing fused score here
                final_rank=0
            ))

        # Sort by final score
        results.sort(key=lambda x: x.rerank_score, reverse=True)

        for i, result in enumerate(results[:top_k]):
            result.final_rank = i + 1

        return results[:top_k]