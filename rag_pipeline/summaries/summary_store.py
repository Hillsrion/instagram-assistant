"""
Storage and search for hierarchical summaries via FAISS.
Manages two separate indexes: one for ConversationSummary, one for PeriodSummary.
"""
import json
import faiss
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple, Union
from dataclasses import dataclass

from rag_pipeline.core.config import Config, default_config
from rag_pipeline.summaries.summary_models import ConversationSummary, PeriodSummary
from rag_pipeline.indexing.embeddings import EmbeddingModel, get_summary_embedding_text


@dataclass
class SummarySearchResult:
    """Search result in summaries."""
    summary: Union[ConversationSummary, PeriodSummary]
    score: float
    level: str  # "conversation" or "period"


class SummaryStore:
    """Storage and search for hierarchical summaries."""

    def __init__(self, config: Config = None, embedding_model: EmbeddingModel = None):
        self.config = config or default_config
        self.embedding_model = embedding_model

        # FAISS Indexes
        self.conversation_index: Optional[faiss.Index] = None
        self.period_index: Optional[faiss.Index] = None

        # Data
        self.conversation_summaries: List[ConversationSummary] = []
        self.period_summaries: List[PeriodSummary] = []

        # Paths
        self.index_path = self.config.index_dir / "summary_index"

    def build_indexes(
        self,
        conversation_summaries: List[ConversationSummary],
        period_summaries: List[PeriodSummary],
        show_progress: bool = True
    ):
        """Builds the two FAISS indexes for summaries."""
        self.conversation_summaries = conversation_summaries
        self.period_summaries = period_summaries

        if not self.embedding_model:
            raise ValueError("EmbeddingModel required to build indexes")

        # 1. ConversationSummary Index
        if conversation_summaries:
            if show_progress:
                print(f"   Encoding {len(conversation_summaries)} conversation summaries...")

            conv_texts = [get_summary_embedding_text(s) for s in conversation_summaries]
            conv_embeddings = self.embedding_model.encode(conv_texts, show_progress=show_progress)

            # Create FAISS index (Inner Product for cosine similarity on normalized vectors)
            dim = conv_embeddings.shape[1]
            self.conversation_index = faiss.IndexFlatIP(dim)

            # Normalize for cosine similarity
            faiss.normalize_L2(conv_embeddings)
            self.conversation_index.add(conv_embeddings)

            if show_progress:
                print(f"   ✓ Conversation index: {self.conversation_index.ntotal} vectors")

        # 2. PeriodSummary Index
        if period_summaries:
            if show_progress:
                print(f"   Encoding {len(period_summaries)} period summaries...")

            period_texts = [get_summary_embedding_text(s) for s in period_summaries]
            period_embeddings = self.embedding_model.encode(period_texts, show_progress=show_progress)

            dim = period_embeddings.shape[1]
            self.period_index = faiss.IndexFlatIP(dim)

            faiss.normalize_L2(period_embeddings)
            self.period_index.add(period_embeddings)

            if show_progress:
                print(f"   ✓ Period index: {self.period_index.ntotal} vectors")

    def search(
        self,
        query: str,
        level: str = "all",
        top_k: int = 3,
        min_score: float = 0.0
    ) -> List[SummarySearchResult]:
        """
        Search in summaries.

        Args:
            query: User question
            level: "conversation", "period", or "all"
            top_k: Number of results per level
            min_score: Minimum score to return a result

        Returns:
            List of SummarySearchResult sorted by score
        """
        if not self.embedding_model:
            raise ValueError("EmbeddingModel required for search")

        # Encode query
        query_embedding = self.embedding_model.encode_single(query)
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(query_embedding)

        results = []

        # Search in ConversationSummary
        if level in ("all", "conversation") and self.conversation_index and self.conversation_index.ntotal > 0:
            k = min(top_k, self.conversation_index.ntotal)
            scores, indices = self.conversation_index.search(query_embedding, k)

            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and score >= min_score:
                    results.append(SummarySearchResult(
                        summary=self.conversation_summaries[idx],
                        score=float(score),
                        level="conversation"
                    ))

        # Search in PeriodSummary
        if level in ("all", "period") and self.period_index and self.period_index.ntotal > 0:
            k = min(top_k, self.period_index.ntotal)
            scores, indices = self.period_index.search(query_embedding, k)

            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and score >= min_score:
                    results.append(SummarySearchResult(
                        summary=self.period_summaries[idx],
                        score=float(score),
                        level="period"
                    ))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)

        return results[:top_k * 2] if level == "all" else results[:top_k]

    def search_by_embedding(
        self,
        query_embedding: np.ndarray,
        level: str = "all",
        top_k: int = 3,
        min_score: float = 0.0
    ) -> List[SummarySearchResult]:
        """
        Search using a pre-computed embedding.

        Args:
            query_embedding: Query vector (already encoded)
            level: "conversation", "period", or "all"
            top_k: Number of results
            min_score: Minimum score

        Returns:
            List of SummarySearchResult
        """
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(query_embedding)

        results = []

        if level in ("all", "conversation") and self.conversation_index and self.conversation_index.ntotal > 0:
            k = min(top_k, self.conversation_index.ntotal)
            scores, indices = self.conversation_index.search(query_embedding, k)

            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and score >= min_score:
                    results.append(SummarySearchResult(
                        summary=self.conversation_summaries[idx],
                        score=float(score),
                        level="conversation"
                    ))

        if level in ("all", "period") and self.period_index and self.period_index.ntotal > 0:
            k = min(top_k, self.period_index.ntotal)
            scores, indices = self.period_index.search(query_embedding, k)

            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and score >= min_score:
                    results.append(SummarySearchResult(
                        summary=self.period_summaries[idx],
                        score=float(score),
                        level="period"
                    ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k * 2] if level == "all" else results[:top_k]

    def save(self):
        """Saves indexes and data."""
        self.index_path.mkdir(parents=True, exist_ok=True)

        # Save FAISS indexes
        if self.conversation_index and self.conversation_index.ntotal > 0:
            faiss.write_index(
                self.conversation_index,
                str(self.index_path / "conversation_index.faiss")
            )

        if self.period_index and self.period_index.ntotal > 0:
            faiss.write_index(
                self.period_index,
                str(self.index_path / "period_index.faiss")
            )

        # Save JSON data
        conv_path = self.config.index_dir / "conversation_summaries.json"
        with open(conv_path, 'w', encoding='utf-8') as f:
            json.dump(
                [s.to_dict() for s in self.conversation_summaries],
                f,
                ensure_ascii=False,
                indent=2
            )

        period_path = self.config.index_dir / "period_summaries.json"
        with open(period_path, 'w', encoding='utf-8') as f:
            json.dump(
                [s.to_dict() for s in self.period_summaries],
                f,
                ensure_ascii=False,
                indent=2
            )

        print(f"   💾 Saved to {self.index_path}")

    def load(self) -> bool:
        """Loads indexes and data."""
        conv_index_path = self.index_path / "conversation_index.faiss"
        period_index_path = self.index_path / "period_index.faiss"
        conv_data_path = self.config.index_dir / "conversation_summaries.json"
        period_data_path = self.config.index_dir / "period_summaries.json"

        # Check if files exist
        if not conv_data_path.exists() and not period_data_path.exists():
            return False

        # Load JSON data
        if conv_data_path.exists():
            with open(conv_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.conversation_summaries = [ConversationSummary.from_dict(d) for d in data]

        if period_data_path.exists():
            with open(period_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.period_summaries = [PeriodSummary.from_dict(d) for d in data]

        # Load FAISS indexes
        if conv_index_path.exists():
            self.conversation_index = faiss.read_index(str(conv_index_path))

        if period_index_path.exists():
            self.period_index = faiss.read_index(str(period_index_path))

        return True

    def get_conversation_summary(self, conversation_id: str) -> Optional[ConversationSummary]:
        """Gets summary for a specific conversation."""
        for summary in self.conversation_summaries:
            if summary.conversation_id == conversation_id:
                return summary
        return None

    def get_period_summaries_for_conversation(
        self,
        conversation_id: str
    ) -> List[PeriodSummary]:
        """Gets all period summaries for a conversation."""
        return [
            s for s in self.period_summaries
            if s.conversation_id == conversation_id
        ]

    def get_summaries_for_participant(
        self,
        participant: str
    ) -> Tuple[List[ConversationSummary], List[PeriodSummary]]:
        """Gets all summaries involving a participant."""
        conv_results = [
            s for s in self.conversation_summaries
            if participant.lower() in [p.lower() for p in s.participants]
        ]
        period_results = [
            s for s in self.period_summaries
            if participant.lower() in [p.lower() for p in s.participants]
        ]
        return conv_results, period_results

    def format_summary_context(self, results: List[SummarySearchResult]) -> str:
        """Formats summaries for inclusion in LLM context."""
        if not results:
            return ""

        parts = []
        for i, result in enumerate(results, 1):
            summary = result.summary

            if isinstance(summary, ConversationSummary):
                header = (
                    f"=== CONVERSATION SUMMARY [{result.level.upper()}] ===\n"
                    f"Participants: {', '.join(summary.participants)}\n"
                    f"Period: {summary.date_start[:10]} → {summary.date_end[:10]}\n"
                    f"Messages: {summary.total_messages} | Chunks: {summary.total_chunks}\n"
                    f"Score: {result.score:.2f}\n"
                    f"---\n"
                    f"Summary: {summary.summary}\n"
                    f"Topics: {', '.join(summary.main_topics)}\n"
                    f"Relationship: {summary.relationship_dynamic}\n"
                    f"Events: {', '.join(summary.notable_events)}"
                )
            else:  # PeriodSummary
                header = (
                    f"=== PERIOD SUMMARY [{result.level.upper()}] ===\n"
                    f"Participants: {', '.join(summary.participants)}\n"
                    f"Period: {summary.period} ({summary.date_start[:10]} → {summary.date_end[:10]})\n"
                    f"Messages: {summary.message_count}\n"
                    f"Score: {result.score:.2f}\n"
                    f"---\n"
                    f"Summary: {summary.summary}\n"
                    f"Topics: {', '.join(summary.topics)}\n"
                    f"Mood: {summary.mood}"
                )

            parts.append(header)

        return "\n\n".join(parts)