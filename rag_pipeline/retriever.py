"""
Retriever for RAG Pipeline.
Handles search and context formatting for the LLM.
"""
from typing import List, Optional
from dataclasses import dataclass

from .config import Config, default_config
from .embeddings import EmbeddingModel
from .vector_store import VectorStore, SearchResult


@dataclass
class RetrievalContext:
    """Retrieval context formatted for the LLM."""
    query: str
    results: List[SearchResult]
    formatted_context: str
    has_results: bool
    
    def get_sources(self) -> List[str]:
        """Returns the list of used sources."""
        sources = []
        for r in self.results:
            source = (
                f"[{r.rank}] {r.chunk.file_source} "
                f"({r.chunk.date_start[:10]} → {r.chunk.date_end[:10]}) "
                f"- Score: {r.score:.2f}"
            )
            sources.append(source)
        return sources


class Retriever:
    """
    Controlled Retriever for RAG.
    Handles search and context formatting.
    """
    
    def __init__(
        self,
        embedding_model: EmbeddingModel,
        vector_store: VectorStore,
        config: Config = None
    ):
        self.config = config or default_config
        self.embedding_model = embedding_model
        self.vector_store = vector_store
    
    def retrieve(
        self,
        query: str,
        top_k: int = None,
        min_score: float = None
    ) -> RetrievalContext:
        """
        Performs a search and returns the formatted context.
        
        Args:
            query: User question
            top_k: Number of results (default: config.top_k)
            min_score: Minimum score (default: config.min_similarity)
            
        Returns:
            RetrievalContext with results and formatted context
        """
        top_k = top_k or self.config.top_k
        min_score = min_score or self.config.min_similarity
        
        # Encode query
        query_embedding = self.embedding_model.encode_single(query)
        
        # Search in vector store
        results = self.vector_store.search(
            query_embedding,
            top_k=top_k,
            min_score=min_score
        )
        
        # Format context
        formatted_context = self._format_context(results)
        
        return RetrievalContext(
            query=query,
            results=results,
            formatted_context=formatted_context,
            has_results=len(results) > 0
        )
    
    def _format_context(self, results: List[SearchResult]) -> str:
        """Formats results into context for the LLM."""
        if not results:
            return "No relevant documents found."
        
        context_parts = []
        
        for result in results:
            chunk = result.chunk
            
            # Document header
            header = (
                f"=== DOCUMENT {result.rank} ===\n"
                f"Source: {chunk.file_source}\n"
                f"Participants: {', '.join(chunk.participants)}\n"
                f"Period: {chunk.date_start[:10]} → {chunk.date_end[:10]}\n"
                f"Relevance Score: {result.score:.2f}\n"
                f"---\n"
            )
            
            # Content - no truncation needed for 256k context
            # (Instagram chunks rarely exceed 10k chars)
            content = chunk.content
            
            context_parts.append(header + content)
        
        return "\n\n".join(context_parts)
    
    def retrieve_with_filter(
        self,
        query: str,
        participant_filter: Optional[str] = None,
        date_filter: Optional[str] = None,
        top_k: int = None
    ) -> RetrievalContext:
        """
        Search with optional filters on results.
        
        Note: Filters are applied post-retrieval because FAISS
        does not natively support metadata filtering.
        """
        # Fetch more results to filter later
        top_k = top_k or self.config.top_k
        extended_k = top_k * 3
        
        context = self.retrieve(query, top_k=extended_k, min_score=0.2)
        
        # Apply filters
        filtered_results = []
        for result in context.results:
            # Filter by participant
            if participant_filter:
                participant_lower = participant_filter.lower()
                participants_lower = [p.lower() for p in result.chunk.participants]
                if not any(participant_lower in p for p in participants_lower):
                    continue
            
            # Filter by date (format: YYYY or YYYY-MM)
            if date_filter:
                if not (date_filter in result.chunk.date_start or 
                        date_filter in result.chunk.date_end):
                    continue
            
            filtered_results.append(result)
            
            if len(filtered_results) >= top_k:
                break
        
        # Reformat context with filtered results
        formatted_context = self._format_context(filtered_results)
        
        return RetrievalContext(
            query=query,
            results=filtered_results,
            formatted_context=formatted_context,
            has_results=len(filtered_results) > 0
        )