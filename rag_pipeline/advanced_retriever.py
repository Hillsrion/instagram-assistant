"""
Retriever avancé avec toutes les améliorations:
- Reranking cross-encoder
- Context expansion (chunks adjacents)
- Hybrid search (BM25 + dense)
- Pre-filtering par métadonnées
"""
import numpy as np
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass, field

from .config import Config, default_config
from .chunker import Chunk
from .embeddings import EmbeddingModel
from .vector_store import VectorStore, SearchResult
from .reranker import CrossEncoderReranker, RerankResult
from .bm25_index import BM25Index
from .metadata_store import MetadataStore
from .summary_store import SummaryStore, SummarySearchResult
from .query_extractor import QueryDateExtractor


@dataclass
class AdvancedSearchResult:
    """Résultat de recherche avancée."""
    chunk: Chunk
    dense_score: float
    bm25_score: float
    rerank_score: float
    final_score: float
    rank: int
    is_expanded: bool = False  # True si ajouté par context expansion


@dataclass
class AdvancedRetrievalContext:
    """Contexte de retrieval avancé."""
    query: str
    results: List[AdvancedSearchResult]
    formatted_context: str
    has_results: bool
    filters_applied: dict = field(default_factory=dict)
    search_mode: str = "hybrid"  # dense, bm25, hybrid
    low_confidence: bool = False  # True if max score < confidence_threshold
    max_confidence_score: float = 0.0  # Highest score among results
    # Summary fallback fields
    summary_results: List[SummarySearchResult] = field(default_factory=list)
    used_summary_fallback: bool = False

    def get_sources(self) -> List[str]:
        """Retourne la liste des sources."""
        sources = []
        for r in self.results:
            expanded = " [expanded]" if r.is_expanded else ""
            source = (
                f"[{r.rank}] {r.chunk.file_source} "
                f"({r.chunk.date_start[:10]})\n"
                f"    📝 {r.chunk.narrative_summary if r.chunk.narrative_summary else r.chunk.summary}\n"
                f"    🎯 Score: {r.final_score:.2f}{expanded}"
            )
            sources.append(source)
        return sources


class AdvancedRetriever:
    """
    Retriever avancé avec:
    - Hybrid search (dense + BM25)
    - Cross-encoder reranking
    - Context expansion
    - Pre-filtering par métadonnées
    """

    def __init__(
        self,
        embedding_model: EmbeddingModel,
        vector_store: VectorStore,
        bm25_index: Optional[BM25Index] = None,
        metadata_store: Optional[MetadataStore] = None,
        reranker: Optional[CrossEncoderReranker] = None,
        summary_store: Optional[SummaryStore] = None,
        config: Config = None
    ):
        self.config = config or default_config
        self.embedding_model = embedding_model
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.metadata_store = metadata_store
        self.reranker = reranker
        self.summary_store = summary_store
        self.date_extractor = QueryDateExtractor(self.config)

        # Configuration par défaut
        self.default_top_k = 5
        self.initial_k = 20  # Pour le reranking
        self.hybrid_alpha = 0.5  # Poids dense vs BM25
        self.context_window = 1  # Chunks adjacents
        self.fallback_threshold = self.config.fallback_threshold  # Seuil pour fallback summaries

    def retrieve(
        self,
        query: str,
        top_k: int = None,
        min_score: float = None,
        # Filtres
        participant_filter: Optional[str] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        year_filter: Optional[int] = None,
        conversation_filter: Optional[str] = None,
        # Options
        use_reranking: bool = True,
        use_hybrid: bool = True,
        expand_context: bool = True,
        search_mode: str = "auto"  # auto, dense, bm25, hybrid
    ) -> AdvancedRetrievalContext:
        """
        Recherche avancée avec toutes les options.

        Args:
            query: Question de l'utilisateur
            top_k: Nombre final de résultats
            min_score: Score minimum
            participant_filter: Filtrer par participant
            date_start/date_end: Filtrer par période
            year_filter: Filtrer par année
            conversation_filter: Filtrer par conversation
            use_reranking: Utiliser le cross-encoder
            use_hybrid: Combiner dense + BM25
            expand_context: Ajouter les chunks adjacents
            search_mode: Force un mode de recherche

        Returns:
            AdvancedRetrievalContext avec les résultats
        """
        top_k = top_k or self.default_top_k
        min_score = min_score or self.config.min_similarity

        filters_applied = {}

        # ========================================
        # Étape 0: Extraction temporelle automatique
        # ========================================
        # Si aucune date n'est fournie explicitement, on essaie de la deviner
        if not date_start and not date_end and not year_filter:
            extracted_start, extracted_end = self.date_extractor.extract_dates(query)
            if extracted_start or extracted_end:
                date_start = extracted_start
                date_end = extracted_end
                print(f"🕒 Période détectée: {date_start} -> {date_end}")

        # ========================================
        # Étape 1: Pre-filtering par métadonnées
        # ========================================
        allowed_indices: Optional[Set[int]] = None

        if self.metadata_store and any([
            participant_filter, date_start, date_end, year_filter, conversation_filter
        ]):
            allowed_indices = None

            if participant_filter:
                allowed_indices = self.metadata_store.filter_by_participant(
                    participant_filter, allowed_indices
                )
                filters_applied['participant'] = participant_filter

            if date_start or date_end:
                allowed_indices = self.metadata_store.filter_by_date_range(
                    date_start, date_end, allowed_indices
                )
                if date_start:
                    filters_applied['date_start'] = date_start
                if date_end:
                    filters_applied['date_end'] = date_end

            if year_filter:
                allowed_indices = self.metadata_store.filter_by_year(
                    year_filter, allowed_indices
                )
                filters_applied['year'] = year_filter

            if conversation_filter:
                allowed_indices = self.metadata_store.filter_by_conversation(
                    conversation_filter, allowed_indices
                )
                filters_applied['conversation'] = conversation_filter

            if allowed_indices is not None and len(allowed_indices) == 0:
                return AdvancedRetrievalContext(
                    query=query,
                    results=[],
                    formatted_context="Aucun document ne correspond aux filtres appliqués.",
                    has_results=False,
                    filters_applied=filters_applied,
                    search_mode="filtered_empty"
                )

        # ========================================
        # Étape 2: Recherche (dense, BM25, ou hybrid)
        # ========================================

        # Déterminer le mode de recherche
        if search_mode == "auto":
            if use_hybrid and self.bm25_index:
                search_mode = "hybrid"
            else:
                search_mode = "dense"

        # Nombre de candidats à récupérer (plus si reranking)
        fetch_k = self.initial_k if (use_reranking and self.reranker) else top_k * 2

        candidates: List[Tuple[int, float, float, float]] = []  # (idx, dense, bm25, combined)

        if search_mode == "dense":
            candidates = self._search_dense(query, fetch_k, allowed_indices)
        elif search_mode == "bm25":
            candidates = self._search_bm25(query, fetch_k, allowed_indices)
        else:  # hybrid
            candidates = self._search_hybrid(query, fetch_k, allowed_indices)

        if not candidates:
            return AdvancedRetrievalContext(
                query=query,
                results=[],
                formatted_context="Aucun document pertinent trouvé.",
                has_results=False,
                filters_applied=filters_applied,
                search_mode=search_mode
            )

        # ========================================
        # Étape 3: Reranking (optionnel)
        # ========================================
        if use_reranking and self.reranker and len(candidates) > 1:
            candidates = self._apply_reranking(query, candidates, top_k)
        else:
            # Garder les top_k
            candidates = candidates[:top_k]

        # ========================================
        # Étape 4: Context expansion (optionnel)
        # ========================================
        if expand_context and self.metadata_store:
            candidates = self._expand_context(candidates)

        # ========================================
        # Étape 5: Construire les résultats
        # ========================================
        results = []
        seen_chunk_ids = set()

        for rank, (idx, dense_score, bm25_score, final_score, is_expanded) in enumerate(candidates):
            chunk = self.vector_store.chunks[idx]

            # Éviter les doublons
            if chunk.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.chunk_id)

            # Filtrer par score minimum (sauf pour les expanded)
            if not is_expanded and final_score < min_score:
                continue

            results.append(AdvancedSearchResult(
                chunk=chunk,
                dense_score=dense_score,
                bm25_score=bm25_score,
                rerank_score=final_score,
                final_score=final_score,
                rank=len(results) + 1,
                is_expanded=is_expanded
            ))

        # Compute confidence score
        max_confidence_score = max((r.final_score for r in results), default=0.0)
        low_confidence = max_confidence_score < self.config.confidence_threshold if results else True

        # ========================================
        # Étape 6: Fallback vers résumés si confiance basse
        # ========================================
        summary_results = []
        used_summary_fallback = False

        if max_confidence_score < self.fallback_threshold and self.summary_store:
            # Rechercher dans les résumés hiérarchiques
            query_embedding = self.embedding_model.encode_single(query)
            summary_results = self.summary_store.search_by_embedding(
                query_embedding,
                level="all",
                top_k=3,
                min_score=0.2
            )
            if summary_results:
                used_summary_fallback = True

        # Formater le contexte (inclut les résumés si fallback)
        formatted_context = self._format_context(results, summary_results)

        return AdvancedRetrievalContext(
            query=query,
            results=results,
            formatted_context=formatted_context,
            has_results=len(results) > 0 or len(summary_results) > 0,
            filters_applied=filters_applied,
            search_mode=search_mode,
            low_confidence=low_confidence,
            max_confidence_score=max_confidence_score,
            summary_results=summary_results,
            used_summary_fallback=used_summary_fallback
        )

    def _search_dense(
        self,
        query: str,
        top_k: int,
        allowed_indices: Optional[Set[int]]
    ) -> List[Tuple[int, float, float, float, bool]]:
        """Recherche dense uniquement."""
        query_embedding = self.embedding_model.encode_single(query)

        # Récupérer plus de résultats si on filtre
        fetch_k = top_k * 3 if allowed_indices else top_k

        results = self.vector_store.search(query_embedding, top_k=fetch_k, min_score=0.1)

        candidates = []
        for r in results:
            idx = self.vector_store.chunks.index(r.chunk)

            if allowed_indices and idx not in allowed_indices:
                continue

            candidates.append((idx, r.score, 0.0, r.score, False))

            if len(candidates) >= top_k:
                break

        return candidates

    def _search_bm25(
        self,
        query: str,
        top_k: int,
        allowed_indices: Optional[Set[int]]
    ) -> List[Tuple[int, float, float, float, bool]]:
        """Recherche BM25 uniquement."""
        if not self.bm25_index:
            return []

        results = self.bm25_index.search(query, top_k=top_k * 3)

        candidates = []
        for idx, score in results:
            if allowed_indices and idx not in allowed_indices:
                continue

            candidates.append((idx, 0.0, score, score, False))

            if len(candidates) >= top_k:
                break

        return candidates

    def _search_hybrid(
        self,
        query: str,
        top_k: int,
        allowed_indices: Optional[Set[int]]
    ) -> List[Tuple[int, float, float, float, bool]]:
        """Recherche hybride (dense + BM25)."""
        # Dense search
        query_embedding = self.embedding_model.encode_single(query)
        dense_results = self.vector_store.search(query_embedding, top_k=top_k * 3, min_score=0.0)

        # BM25 search
        if self.bm25_index:
            bm25_scores = self.bm25_index.get_scores_array(query)
        else:
            bm25_scores = np.zeros(len(self.vector_store.chunks))

        # Construire un dictionnaire des scores dense
        dense_dict = {}
        for r in dense_results:
            idx = self.vector_store.chunks.index(r.chunk)
            dense_dict[idx] = r.score

        # Fusionner les scores
        all_indices = set(dense_dict.keys())
        if self.bm25_index:
            # Ajouter les indices avec un score BM25 significatif
            bm25_top = np.argsort(bm25_scores)[-top_k * 3:]
            all_indices.update(bm25_top)

        # Normaliser et combiner
        dense_values = np.array([dense_dict.get(i, 0.0) for i in all_indices])
        bm25_values = np.array([bm25_scores[i] for i in all_indices])
        indices = list(all_indices)

        # Min-max normalization
        if dense_values.max() > dense_values.min():
            dense_norm = (dense_values - dense_values.min()) / (dense_values.max() - dense_values.min())
        else:
            dense_norm = dense_values

        if bm25_values.max() > bm25_values.min():
            bm25_norm = (bm25_values - bm25_values.min()) / (bm25_values.max() - bm25_values.min())
        else:
            bm25_norm = bm25_values

        # Fusion avec alpha
        combined = self.hybrid_alpha * dense_norm + (1 - self.hybrid_alpha) * bm25_norm

        # Trier par score combiné
        sorted_indices = np.argsort(combined)[::-1]

        candidates = []
        for i in sorted_indices:
            idx = indices[i]

            if allowed_indices and idx not in allowed_indices:
                continue

            candidates.append((
                idx,
                float(dense_values[i]),
                float(bm25_values[i]),
                float(combined[i]),
                False
            ))

            if len(candidates) >= top_k:
                break

        return candidates

    def _apply_reranking(
        self,
        query: str,
        candidates: List[Tuple[int, float, float, float, bool]],
        top_k: int
    ) -> List[Tuple[int, float, float, float, bool]]:
        """Applique le reranking cross-encoder avec fusion des scores."""
        # Préparer les paires pour le reranker
        # On passe le score combiné (hybrid) comme score de densité
        chunks_for_rerank = [(self.vector_store.chunks[idx], score) for idx, _, _, score, _ in candidates]

        # Utiliser rerank_with_fusion pour combiner les scores correctement
        # (dense + rerank avec normalisation)
        reranked = self.reranker.rerank_with_fusion(
            query,
            chunks_for_rerank,
            top_k=top_k,
            alpha=0.5  # Équilibre entre score hybride (50%) et reranker (50%)
        )

        # Reconstruire la liste avec les nouveaux scores fusionnés
        result = []
        for rr in reranked:
            # Retrouver l'index
            for idx, dense, bm25, combined, expanded in candidates:
                if self.vector_store.chunks[idx].chunk_id == rr.chunk.chunk_id:
                    # rr.rerank_score contient maintenant le score fusionné normalisé
                    result.append((idx, dense, bm25, rr.rerank_score, expanded))
                    break

        return result

    def _expand_context(
        self,
        candidates: List[Tuple[int, float, float, float, bool]]
    ) -> List[Tuple[int, float, float, float, bool]]:
        """Ajoute les chunks adjacents (context expansion)."""
        expanded = list(candidates)
        seen_indices = {c[0] for c in candidates}

        for idx, dense, bm25, score, _ in candidates:
            chunk = self.vector_store.chunks[idx]
            adjacent_indices = self.metadata_store.get_adjacent_chunks(
                chunk.chunk_id,
                window=self.context_window
            )

            for adj_idx in adjacent_indices:
                if adj_idx not in seen_indices:
                    seen_indices.add(adj_idx)
                    # Score réduit pour les chunks expandés
                    expanded.append((adj_idx, 0.0, 0.0, score * 0.5, True))

        return expanded

    def _format_context(
        self,
        results: List[AdvancedSearchResult],
        summary_results: List[SummarySearchResult] = None
    ) -> str:
        """Formate les résultats en contexte pour le LLM."""
        context_parts = []

        # Ajouter les résumés hiérarchiques en premier (vue d'ensemble)
        if summary_results:
            context_parts.append("=== RÉSUMÉS GLOBAUX (VUE D'ENSEMBLE) ===\n")
            summary_context = self.summary_store.format_summary_context(summary_results)
            context_parts.append(summary_context)
            context_parts.append("\n" + "=" * 50 + "\n")

        if not results and not summary_results:
            return "Aucun document pertinent trouvé."

        # Ajouter les chunks détaillés
        for result in results:
            chunk = result.chunk
            expanded_tag = " [CONTEXTE ADJACENT]" if result.is_expanded else ""

            header = (
                f"=== DOCUMENT {result.rank}{expanded_tag} ===\n"
                f"Source: {chunk.file_source}\n"
                f"Participants: {', '.join(chunk.participants)}\n"
                f"Période: {chunk.date_start[:10]} → {chunk.date_end[:10]}\n"
                f"Score: {result.final_score:.2f}\n"
                f"---\n"
            )

            content = chunk.content
            max_chars = 2500 if not result.is_expanded else 1500
            if len(content) > max_chars:
                content = content[:max_chars] + "\n[... tronqué ...]"

            context_parts.append(header + content)

        return "\n\n".join(context_parts)


def create_advanced_retriever(
    config: Config = None,
    enable_reranking: bool = True,
    enable_bm25: bool = True,
    enable_metadata: bool = True,
    enable_summaries: bool = True
) -> Tuple[AdvancedRetriever, dict]:
    """
    Factory pour créer un AdvancedRetriever avec toutes ses dépendances.

    Returns:
        (retriever, components_dict)
    """
    config = config or default_config

    # Charger les composants
    from .embeddings import EmbeddingModel
    from .vector_store import VectorStore

    embedding_model = EmbeddingModel(config)
    vector_store = VectorStore(config)

    if not vector_store.load():
        raise RuntimeError("Index FAISS non trouvé. Lancez d'abord setup_rag_batch.py")

    components = {
        'embedding_model': embedding_model,
        'vector_store': vector_store,
    }

    # BM25
    bm25_index = None
    if enable_bm25:
        bm25_index = BM25Index(config)
        if not bm25_index.load():
            print("⚠️  Index BM25 non trouvé, construction...")
            bm25_index.chunks = vector_store.chunks
            bm25_index.build_index(vector_store.chunks)
            bm25_index.save()
        else:
            # Assign chunks after successful load
            bm25_index.chunks = vector_store.chunks
        components['bm25_index'] = bm25_index

    # Metadata store
    metadata_store = None
    if enable_metadata:
        metadata_store = MetadataStore(config)
        if not (config.index_dir / "metadata.db").exists():
            print("⚠️  Index métadonnées non trouvé, construction...")
            metadata_store.build_index(vector_store.chunks)
        components['metadata_store'] = metadata_store

    # Reranker
    reranker = None
    if enable_reranking:
        reranker = CrossEncoderReranker(config)
        components['reranker'] = reranker

    # Summary store (hierarchical summaries)
    summary_store = None
    if enable_summaries:
        summary_store = SummaryStore(config, embedding_model)
        if summary_store.load():
            print(f"✅ Summary index chargé: {len(summary_store.conversation_summaries)} conversations, {len(summary_store.period_summaries)} périodes")
            components['summary_store'] = summary_store
        else:
            print("⚠️  Index des résumés non trouvé. Lancez setup_rag_batch.py pour le générer.")
            summary_store = None

    retriever = AdvancedRetriever(
        embedding_model=embedding_model,
        vector_store=vector_store,
        bm25_index=bm25_index,
        metadata_store=metadata_store,
        reranker=reranker,
        summary_store=summary_store,
        config=config
    )

    return retriever, components
