"""Advanced Retriever with all improvements:
- Cross-encoder reranking
- Context expansion (adjacent chunks)
- Hybrid search (BM25 + dense)
- Metadata pre-filtering
"""
import numpy as np
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass, field

from rag_pipeline.core.config import Config, default_config
from rag_pipeline.core.models import Chunk
from rag_pipeline.indexing.embeddings import EmbeddingModel
from rag_pipeline.indexing.vector_store import VectorStore, SearchResult
from rag_pipeline.query.reranker import CrossEncoderReranker, RerankResult
from rag_pipeline.indexing.bm25_index import BM25Index
from rag_pipeline.indexing.metadata_store import MetadataStore
from rag_pipeline.summaries.summary_store import SummaryStore, SummarySearchResult
from rag_pipeline.query.query_extractor import QueryDateExtractor


@dataclass
class AdvancedSearchResult:
    """Advanced search result."""
    chunk: Chunk
    dense_score: float
    bm25_score: float
    rerank_score: float
    final_score: float
    rank: int
    is_expanded: bool = False  # True if added by context expansion


@dataclass
class AdvancedRetrievalContext:
    """Advanced retrieval context."""
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
        """Returns the list of sources."""
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
    Advanced Retriever with:
    - Hybrid search (dense + BM25)
    - Cross-encoder reranking
    - Context expansion
    - Metadata pre-filtering
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

        # Default configuration
        self.default_top_k = 5
        self.initial_k = 20  # For reranking
        self.hybrid_alpha = 0.5  # Dense vs BM25 weight
        self.context_window = 1  # Adjacent chunks
        self.fallback_threshold = self.config.fallback_threshold  # Threshold for summary fallback

    def retrieve(
        self,
        query: str,
        top_k: int = None,
        min_score: float = None,
        # Filters
        participant_filter: Optional[str] = None,
        about_person: Optional[str] = None,
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
        Advanced search with all options.

        Args:
            query: User question
            top_k: Final number of results
            min_score: Minimum score
            participant_filter: Filter by participant (strict: must be in conversation)
            about_person: Filter by person mentioned (broad: participant OR entity)
            date_start/date_end: Filter by period
            year_filter: Filter by year
            conversation_filter: Filter by conversation
            use_reranking: Use cross-encoder
            use_hybrid: Combine dense + BM25
            expand_context: Add adjacent chunks
            search_mode: Force a search mode

        Returns:
            AdvancedRetrievalContext with results
        """
        top_k = top_k or self.default_top_k
        min_score = min_score or self.config.min_similarity

        filters_applied = {}

        # ========================================
        # Step 0: Automatic temporal extraction
        # ========================================
        # If no date explicitly provided, try to guess
        if not date_start and not date_end and not year_filter:
            extracted_start, extracted_end = self.date_extractor.extract_dates(query)
            if extracted_start or extracted_end:
                date_start = extracted_start
                date_end = extracted_end
                print(f"🕒 Period detected: {date_start} -> {date_end}")

        # ========================================
        # Step 1: Metadata Pre-filtering
        # ========================================
        allowed_indices: Optional[Set[int]] = None

        if self.metadata_store and any([
            participant_filter, about_person, date_start, date_end, year_filter, conversation_filter
        ]):
            allowed_indices = None

            if participant_filter:
                allowed_indices = self.metadata_store.filter_by_participant(
                    participant_filter, allowed_indices
                )
                filters_applied['participant'] = participant_filter

            if about_person:
                allowed_indices = self.metadata_store.filter_by_person(
                    about_person, allowed_indices
                )
                filters_applied['about_person'] = about_person

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
                    formatted_context="No documents match the applied filters.",
                    has_results=False,
                    filters_applied=filters_applied,
                    search_mode="filtered_empty"
                )

        # ========================================
        # Step 2: Search (dense, BM25, or hybrid)
        # ========================================

        # Determine search mode
        if search_mode == "auto":
            if use_hybrid and self.bm25_index:
                search_mode = "hybrid"
            else:
                search_mode = "dense"

        # Number of candidates to fetch (more if reranking)
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
                formatted_context="No relevant documents found.",
                has_results=False,
                filters_applied=filters_applied,
                search_mode=search_mode
            )

        # ========================================
        # Step 3: Reranking (optional)
        # ========================================
        if use_reranking and self.reranker and len(candidates) > 1:
            candidates = self._apply_reranking(query, candidates, top_k)
        else:
            # Keep top_k
            candidates = candidates[:top_k]

        # Filter by min_score BEFORE expansion to avoid expanding irrelevant chunks
        candidates = [c for c in candidates if c[3] >= min_score]

        # ========================================
        # Step 4: Context expansion (optional)
        # ========================================
        if expand_context and self.metadata_store and candidates:
            candidates = self._expand_context(candidates)

        # ========================================
        # Step 5: Build results
        # ========================================
        results = []
        seen_chunk_ids = set()

        for rank, (idx, dense_score, bm25_score, final_score, is_expanded) in enumerate(candidates):
            chunk = self.vector_store.chunks[idx]

            # Avoid duplicates
            if chunk.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.chunk_id)

            # Filter by minimum score (expanded chunks have a lower threshold: min_score * 0.5)
            # This ensures we don't pass completely irrelevant 0.00 chunks to the LLM
            threshold = min_score if not is_expanded else max(0.1, min_score * 0.5)
            if final_score < threshold:
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
        # Step 6: Fallback to summaries if low confidence
        # ========================================
        summary_results = []
        used_summary_fallback = False

        if max_confidence_score < self.fallback_threshold and self.summary_store:
            # Search in hierarchical summaries
            query_embedding = self.embedding_model.encode_single(query)
            summary_results = self.summary_store.search_by_embedding(
                query_embedding,
                level="all",
                top_k=3,
                min_score=0.2
            )
            if summary_results:
                used_summary_fallback = True

        # Format context (includes summaries if fallback)
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
        """Dense search only."""
        query_embedding = self.embedding_model.encode_single(query)

        # Fetch more results if filtering
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
        """BM25 search only."""
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
        """Hybrid search (dense + BM25)."""
        # Dense search
        query_embedding = self.embedding_model.encode_single(query)
        dense_results = self.vector_store.search(query_embedding, top_k=top_k * 3, min_score=0.0)

        # BM25 search
        if self.bm25_index:
            bm25_scores = self.bm25_index.get_scores_array(query)
        else:
            bm25_scores = np.zeros(len(self.vector_store.chunks))

        # Build dictionary of dense scores
        dense_dict = {}
        for r in dense_results:
            idx = self.vector_store.chunks.index(r.chunk)
            dense_dict[idx] = r.score

        # Merge scores
        all_indices = set(dense_dict.keys())
        if self.bm25_index:
            # Add indices with significant BM25 score
            bm25_top = np.argsort(bm25_scores)[-top_k * 3:]
            all_indices.update(bm25_top)

        # Normalize and combine
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

        # Fusion with alpha
        combined = self.hybrid_alpha * dense_norm + (1 - self.hybrid_alpha) * bm25_norm

        # Sort by combined score
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
        """Applies cross-encoder reranking with score fusion."""
        # Prepare pairs for reranker
        # Pass combined (hybrid) score as density score
        chunks_for_rerank = [(self.vector_store.chunks[idx], score) for idx, _, _, score, _ in candidates]

        # Use rerank_with_fusion to combine scores correctly
        # (dense + rerank with normalization)
        reranked = self.reranker.rerank_with_fusion(
            query,
            chunks_for_rerank,
            top_k=top_k,
            alpha=0.5  # Balance between hybrid score (50%) and reranker (50%)
        )

        # Reconstruct list with new fused scores
        result = []
        for rr in reranked:
            # Find index
            for idx, dense, bm25, combined, expanded in candidates:
                if self.vector_store.chunks[idx].chunk_id == rr.chunk.chunk_id:
                    # rr.rerank_score now contains the normalized fused score
                    result.append((idx, dense, bm25, rr.rerank_score, expanded))
                    break

        return result

    def _expand_context(
        self,
        candidates: List[Tuple[int, float, float, float, bool]]
    ) -> List[Tuple[int, float, float, float, bool]]:
        """Adds adjacent chunks (context expansion)."""
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
                    # Reduced score for expanded chunks
                    expanded.append((adj_idx, 0.0, 0.0, score * 0.5, True))

        return expanded

    def _format_context(
        self,
        results: List[AdvancedSearchResult],
        summary_results: List[SummarySearchResult] = None
    ) -> str:
        """Formats results into context for the LLM."""
        context_parts = []

        # Add hierarchical summaries first (overview)
        if summary_results:
            context_parts.append("=== GLOBAL SUMMARIES (OVERVIEW) ===\n")
            summary_context = self.summary_store.format_summary_context(summary_results)
            context_parts.append(summary_context)
            context_parts.append("\n" + "=" * 50 + "\n")

        if not results and not summary_results:
            return "No relevant documents found."

        # Add detailed chunks
        for result in results:
            chunk = result.chunk
            expanded_tag = " [ADJACENT CONTEXT]" if result.is_expanded else ""

            header = (
                f"=== DOCUMENT {result.rank}{expanded_tag} ===\n"
                f"Source: {chunk.file_source}\n"
                f"Participants: {', '.join(chunk.participants)}\n"
                f"Period: {chunk.date_start[:10]} → {chunk.date_end[:10]}\n"
                f"Score: {result.final_score:.2f}\n"
                f"---\n"
            )

            content = chunk.content
            # Only truncate expanded chunks; main chunks pass through fully
            # (Instagram chunks rarely exceed 10k chars)
            if result.is_expanded and len(content) > 10000:
                content = content[:10000] + "\n[... truncated ...]"

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
    Factory to create an AdvancedRetriever with all its dependencies.

    Returns:
        (retriever, components_dict)
    """
    config = config or default_config

    # Load components
    from rag_pipeline.indexing.embeddings import EmbeddingModel
    from rag_pipeline.indexing.vector_store import VectorStore

    embedding_model = EmbeddingModel(config)
    vector_store = VectorStore(config)

    if not vector_store.load():
        raise RuntimeError("FAISS index not found. Run setup_rag_batch.py first")

    components = {
        'embedding_model': embedding_model,
        'vector_store': vector_store,
    }

    # BM25
    bm25_index = None
    if enable_bm25:
        bm25_index = BM25Index(config)
        if not bm25_index.load():
            print("⚠️  BM25 index not found, building...")
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
            print("⚠️  Metadata index not found, building...")
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
            print(f"✅ Summary index loaded: {len(summary_store.conversation_summaries)} conversations, {len(summary_store.period_summaries)} periods")
            components['summary_store'] = summary_store
        else:
            print("⚠️  Summary index not found. Run setup_rag_batch.py to generate it.")
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