"""
Retriever pour le RAG Pipeline.
Gère la recherche et le formatage du contexte pour le LLM.
"""
from typing import List, Optional
from dataclasses import dataclass

from .config import Config, default_config
from .embeddings import EmbeddingModel
from .vector_store import VectorStore, SearchResult


@dataclass
class RetrievalContext:
    """Contexte de retrieval formaté pour le LLM."""
    query: str
    results: List[SearchResult]
    formatted_context: str
    has_results: bool
    
    def get_sources(self) -> List[str]:
        """Retourne la liste des sources utilisées."""
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
    Retriever contrôlé pour le RAG.
    Gère la recherche et le formatage du contexte.
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
        Effectue une recherche et retourne le contexte formaté.
        
        Args:
            query: Question de l'utilisateur
            top_k: Nombre de résultats (défaut: config.top_k)
            min_score: Score minimum (défaut: config.min_similarity)
            
        Returns:
            RetrievalContext avec les résultats et le contexte formaté
        """
        top_k = top_k or self.config.top_k
        min_score = min_score or self.config.min_similarity
        
        # Encoder la requête
        query_embedding = self.embedding_model.encode_single(query)
        
        # Rechercher dans le vector store
        results = self.vector_store.search(
            query_embedding,
            top_k=top_k,
            min_score=min_score
        )
        
        # Formater le contexte
        formatted_context = self._format_context(results)
        
        return RetrievalContext(
            query=query,
            results=results,
            formatted_context=formatted_context,
            has_results=len(results) > 0
        )
    
    def _format_context(self, results: List[SearchResult]) -> str:
        """Formate les résultats en contexte pour le LLM."""
        if not results:
            return "Aucun document pertinent trouvé."
        
        context_parts = []
        
        for result in results:
            chunk = result.chunk
            
            # En-tête du document
            header = (
                f"=== DOCUMENT {result.rank} ===\n"
                f"Source: {chunk.file_source}\n"
                f"Participants: {', '.join(chunk.participants)}\n"
                f"Période: {chunk.date_start[:10]} → {chunk.date_end[:10]}\n"
                f"Score de pertinence: {result.score:.2f}\n"
                f"---\n"
            )
            
            # Contenu
            content = chunk.content
            
            # Limiter la taille si nécessaire (pour ne pas dépasser le contexte LLM)
            max_chars = 3000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n[... tronqué ...]"
            
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
        Recherche avec filtres optionnels sur les résultats.
        
        Note: Les filtres sont appliqués post-retrieval car FAISS
        ne supporte pas nativement les filtres sur métadonnées.
        """
        # Récupérer plus de résultats pour filtrer ensuite
        top_k = top_k or self.config.top_k
        extended_k = top_k * 3
        
        context = self.retrieve(query, top_k=extended_k, min_score=0.2)
        
        # Appliquer les filtres
        filtered_results = []
        for result in context.results:
            # Filtre par participant
            if participant_filter:
                participant_lower = participant_filter.lower()
                participants_lower = [p.lower() for p in result.chunk.participants]
                if not any(participant_lower in p for p in participants_lower):
                    continue
            
            # Filtre par date (format: YYYY ou YYYY-MM)
            if date_filter:
                if not (date_filter in result.chunk.date_start or 
                        date_filter in result.chunk.date_end):
                    continue
            
            filtered_results.append(result)
            
            if len(filtered_results) >= top_k:
                break
        
        # Reformater le contexte avec les résultats filtrés
        formatted_context = self._format_context(filtered_results)
        
        return RetrievalContext(
            query=query,
            results=filtered_results,
            formatted_context=formatted_context,
            has_results=len(filtered_results) > 0
        )
