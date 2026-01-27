"""
Stockage et recherche des résumés hiérarchiques via FAISS.
Gère deux index séparés : un pour ConversationSummary, un pour PeriodSummary.
"""
import json
import faiss
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple, Union
from dataclasses import dataclass

from .config import Config, default_config
from .summary_models import ConversationSummary, PeriodSummary
from .embeddings import EmbeddingModel


@dataclass
class SummarySearchResult:
    """Résultat de recherche dans les résumés."""
    summary: Union[ConversationSummary, PeriodSummary]
    score: float
    level: str  # "conversation" ou "period"


class SummaryStore:
    """Stockage et recherche des résumés hiérarchiques."""

    def __init__(self, config: Config = None, embedding_model: EmbeddingModel = None):
        self.config = config or default_config
        self.embedding_model = embedding_model

        # Index FAISS
        self.conversation_index: Optional[faiss.Index] = None
        self.period_index: Optional[faiss.Index] = None

        # Données
        self.conversation_summaries: List[ConversationSummary] = []
        self.period_summaries: List[PeriodSummary] = []

        # Chemins
        self.index_path = self.config.index_dir / "summary_index"

    def build_indexes(
        self,
        conversation_summaries: List[ConversationSummary],
        period_summaries: List[PeriodSummary],
        show_progress: bool = True
    ):
        """Construit les deux index FAISS pour les résumés."""
        self.conversation_summaries = conversation_summaries
        self.period_summaries = period_summaries

        if not self.embedding_model:
            raise ValueError("EmbeddingModel requis pour construire les index")

        # 1. Index des ConversationSummary
        if conversation_summaries:
            if show_progress:
                print(f"   Encoding {len(conversation_summaries)} conversation summaries...")

            conv_texts = [s.get_embedding_text() for s in conversation_summaries]
            conv_embeddings = self.embedding_model.encode(conv_texts, show_progress=show_progress)

            # Créer l'index FAISS (Inner Product pour cosine similarity sur vecteurs normalisés)
            dim = conv_embeddings.shape[1]
            self.conversation_index = faiss.IndexFlatIP(dim)

            # Normaliser pour cosine similarity
            faiss.normalize_L2(conv_embeddings)
            self.conversation_index.add(conv_embeddings)

            if show_progress:
                print(f"   ✓ Conversation index: {self.conversation_index.ntotal} vectors")

        # 2. Index des PeriodSummary
        if period_summaries:
            if show_progress:
                print(f"   Encoding {len(period_summaries)} period summaries...")

            period_texts = [s.get_embedding_text() for s in period_summaries]
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
        Recherche dans les résumés.

        Args:
            query: Question de l'utilisateur
            level: "conversation", "period", ou "all"
            top_k: Nombre de résultats par niveau
            min_score: Score minimum pour retourner un résultat

        Returns:
            Liste de SummarySearchResult triée par score
        """
        if not self.embedding_model:
            raise ValueError("EmbeddingModel requis pour la recherche")

        # Encoder la requête
        query_embedding = self.embedding_model.encode_single(query)
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(query_embedding)

        results = []

        # Recherche dans les ConversationSummary
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

        # Recherche dans les PeriodSummary
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

        # Trier par score décroissant
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
        Recherche avec un embedding pré-calculé.

        Args:
            query_embedding: Vecteur de la requête (déjà encodé)
            level: "conversation", "period", ou "all"
            top_k: Nombre de résultats
            min_score: Score minimum

        Returns:
            Liste de SummarySearchResult
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
        """Sauvegarde les index et les données."""
        self.index_path.mkdir(parents=True, exist_ok=True)

        # Sauvegarder les index FAISS
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

        # Sauvegarder les données JSON
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
        """Charge les index et les données."""
        conv_index_path = self.index_path / "conversation_index.faiss"
        period_index_path = self.index_path / "period_index.faiss"
        conv_data_path = self.config.index_dir / "conversation_summaries.json"
        period_data_path = self.config.index_dir / "period_summaries.json"

        # Vérifier que les fichiers existent
        if not conv_data_path.exists() and not period_data_path.exists():
            return False

        # Charger les données JSON
        if conv_data_path.exists():
            with open(conv_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.conversation_summaries = [ConversationSummary.from_dict(d) for d in data]

        if period_data_path.exists():
            with open(period_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.period_summaries = [PeriodSummary.from_dict(d) for d in data]

        # Charger les index FAISS
        if conv_index_path.exists():
            self.conversation_index = faiss.read_index(str(conv_index_path))

        if period_index_path.exists():
            self.period_index = faiss.read_index(str(period_index_path))

        return True

    def get_conversation_summary(self, conversation_id: str) -> Optional[ConversationSummary]:
        """Récupère le résumé d'une conversation spécifique."""
        for summary in self.conversation_summaries:
            if summary.conversation_id == conversation_id:
                return summary
        return None

    def get_period_summaries_for_conversation(
        self,
        conversation_id: str
    ) -> List[PeriodSummary]:
        """Récupère tous les résumés de période pour une conversation."""
        return [
            s for s in self.period_summaries
            if s.conversation_id == conversation_id
        ]

    def get_summaries_for_participant(
        self,
        participant: str
    ) -> Tuple[List[ConversationSummary], List[PeriodSummary]]:
        """Récupère tous les résumés impliquant un participant."""
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
        """Formate les résumés pour inclusion dans le contexte LLM."""
        if not results:
            return ""

        parts = []
        for i, result in enumerate(results, 1):
            summary = result.summary

            if isinstance(summary, ConversationSummary):
                header = (
                    f"=== RÉSUMÉ CONVERSATION [{result.level.upper()}] ===\n"
                    f"Participants: {', '.join(summary.participants)}\n"
                    f"Période: {summary.date_start[:10]} → {summary.date_end[:10]}\n"
                    f"Messages: {summary.total_messages} | Chunks: {summary.total_chunks}\n"
                    f"Score: {result.score:.2f}\n"
                    f"---\n"
                    f"Résumé: {summary.summary}\n"
                    f"Sujets: {', '.join(summary.main_topics)}\n"
                    f"Relation: {summary.relationship_dynamic}\n"
                    f"Événements: {', '.join(summary.notable_events)}"
                )
            else:  # PeriodSummary
                header = (
                    f"=== RÉSUMÉ PÉRIODE [{result.level.upper()}] ===\n"
                    f"Participants: {', '.join(summary.participants)}\n"
                    f"Période: {summary.period} ({summary.date_start[:10]} → {summary.date_end[:10]})\n"
                    f"Messages: {summary.message_count}\n"
                    f"Score: {result.score:.2f}\n"
                    f"---\n"
                    f"Résumé: {summary.summary}\n"
                    f"Sujets: {', '.join(summary.topics)}\n"
                    f"Ambiance: {summary.mood}"
                )

            parts.append(header)

        return "\n\n".join(parts)
