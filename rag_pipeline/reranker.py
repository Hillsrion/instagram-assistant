"""
Reranker Cross-Encoder pour améliorer la précision du retrieval.
Utilise BGE-reranker pour reordonner les candidats après le retrieval dense.
"""
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass

from .config import Config, default_config
from .chunker import Chunk


@dataclass
class RerankResult:
    """Résultat après reranking."""
    chunk: Chunk
    dense_score: float
    rerank_score: float
    final_rank: int


class CrossEncoderReranker:
    """
    Reranker basé sur un cross-encoder.

    Le cross-encoder prend (query, document) en entrée et produit
    un score de pertinence plus précis que la similarité cosinus.
    """

    def __init__(self, config: Config = None, model_name: str = None):
        self.config = config or default_config
        self.model_name = model_name or "BAAI/bge-reranker-base"
        self.model = None
        self._device = None

    def _load_model(self):
        """Charge le modèle cross-encoder (lazy loading)."""
        if self.model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder
            import torch
        except ImportError:
            raise ImportError(
                "sentence-transformers est requis. "
                "Installez avec: pip install sentence-transformers"
            )

        # Déterminer le device
        if self.config.use_gpu and torch.cuda.is_available():
            self._device = "cuda"
        elif self.config.use_gpu and torch.backends.mps.is_available():
            self._device = "mps"
        else:
            self._device = "cpu"

        print(f"📦 Chargement du reranker {self.model_name}...")
        print(f"🖥️  Device: {self._device}")

        self.model = CrossEncoder(
            self.model_name,
            device=self._device,
            max_length=512  # Limite pour éviter les OOM
        )

        print("✅ Reranker chargé")

    def rerank(
        self,
        query: str,
        candidates: List[Tuple[Chunk, float]],  # (chunk, dense_score)
        top_k: int = 5
    ) -> List[RerankResult]:
        """
        Rerank les candidats en utilisant le cross-encoder.

        Args:
            query: Question de l'utilisateur
            candidates: Liste de (chunk, dense_score) triée par dense_score
            top_k: Nombre de résultats à retourner

        Returns:
            Liste de RerankResult triés par rerank_score
        """
        if not candidates:
            return []

        self._load_model()

        # Préparer les paires (query, document)
        pairs = []
        for chunk, _ in candidates:
            # Construction optimale pour le Cross-Encoder
            text_parts = []
            
            # 1. Questions hypothétiques (Trèèès fort signal si match)
            if chunk.hypothetical_questions:
                # On concatène les questions pour que le reranker voie la similarité
                text_parts.append("Questions abordées: " + " ".join(chunk.hypothetical_questions))
            
            # 2. Contexte temporel (Signal temporel)
            if chunk.temporal_context:
                text_parts.append(f"Période: {chunk.temporal_context}")

            # 3. Intentions des participants
            if chunk.speaker_intents:
                intents_str = ", ".join(f"{p}: {i}" for p, i in chunk.speaker_intents.items())
                text_parts.append(f"Intentions: {intents_str}")

            # 4. Émotions (Contexte émotionnel)
            if chunk.emotions:
                emotion_parts = []
                if chunk.emotions.get("dominant"):
                    emotion_parts.append(chunk.emotions["dominant"])
                if chunk.emotions.get("tone"):
                    emotion_parts.append(f"ton {chunk.emotions['tone']}")
                if chunk.emotions.get("tension_level"):
                    emotion_parts.append(f"tension {chunk.emotions['tension_level']}")
                if emotion_parts:
                    text_parts.append(f"Ambiance: {', '.join(emotion_parts)}")

            # 5. Résumé Narratif (Contexte fort)
            if chunk.narrative_summary:
                text_parts.append(f"Résumé: {chunk.narrative_summary}")
            else:
                text_parts.append(f"Résumé: {chunk.summary}")

            # 6. Contenu (Preuve)
            # On garde un extrait significatif (900 chars) pour compenser les nouveaux champs
            text_parts.append(chunk.content[:900])
            
            doc_text = "\n".join(text_parts)
            pairs.append([query, doc_text])

        # Obtenir les scores du cross-encoder
        rerank_scores = self.model.predict(pairs, show_progress_bar=False)

        # Combiner avec les scores denses et trier
        results = []
        for i, ((chunk, dense_score), rerank_score) in enumerate(zip(candidates, rerank_scores)):
            results.append(RerankResult(
                chunk=chunk,
                dense_score=dense_score,
                rerank_score=float(rerank_score),
                final_rank=0  # Sera mis à jour après tri
            ))

        # Trier par rerank_score
        results.sort(key=lambda x: x.rerank_score, reverse=True)

        # Mettre à jour les rangs et limiter
        for i, result in enumerate(results[:top_k]):
            result.final_rank = i + 1

        return results[:top_k]

    def rerank_with_fusion(
        self,
        query: str,
        candidates: List[Tuple[Chunk, float]],
        top_k: int = 5,
        alpha: float = 0.3  # Poids du dense score (1-alpha = poids rerank)
    ) -> List[RerankResult]:
        """
        Rerank avec fusion des scores (dense + rerank).

        Formule: final_score = alpha * dense_score + (1-alpha) * rerank_score
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

        # Normaliser les scores pour la fusion
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

        # Créer les résultats
        results = []
        for i, ((chunk, dense_score), rerank_score, final_score) in enumerate(
            zip(candidates, rerank_scores, final_scores)
        ):
            results.append(RerankResult(
                chunk=chunk,
                dense_score=dense_score,
                rerank_score=float(final_score),  # On stocke le score fusionné ici
                final_rank=0
            ))

        # Trier par score final
        results.sort(key=lambda x: x.rerank_score, reverse=True)

        for i, result in enumerate(results[:top_k]):
            result.final_rank = i + 1

        return results[:top_k]
