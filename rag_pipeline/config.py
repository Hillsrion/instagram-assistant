"""
Configuration centralisée du RAG Pipeline.
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

@dataclass
class Config:
    """Configuration du pipeline RAG."""
    
    # === Chemins ===
    base_dir: Path = Path("/Users/ismaelsebbane/dev/lab/instagram-assistant")
    conversations_dir: Path = field(default=None)
    index_dir: Path = field(default=None)
    vector_store_path: Path = field(default=None)
    chunks_cache_path: Path = field(default=None)
    
    # === Chunking ===
    # Nombre max de messages par chunk
    chunk_max_messages: int = 50
    # Durée max d'un chunk en jours (prioritaire sur max_messages)
    chunk_max_days: int = 3
    # Chevauchement entre chunks (en messages)
    chunk_overlap: int = 5
    
    # === Embeddings ===
    # Modèle d'embeddings (bge-m3 recommandé pour multilingue)
    embedding_model: str = "BAAI/bge-m3"
    # Dimension des embeddings (1024 pour bge-m3)
    embedding_dim: int = 1024
    # Utiliser GPU si disponible
    use_gpu: bool = True
    
    # === Retrieval ===
    # Nombre de chunks à récupérer
    top_k: int = 5
    # Score minimum de similarité (cosine)
    min_similarity: float = 0.3

    # === Advanced Retrieval ===
    # Nombre initial de candidats pour le reranking
    initial_k: int = 20
    # Poids de la recherche dense vs BM25 (0.5 = équilibré)
    hybrid_alpha: float = 0.5
    # Fenêtre de context expansion (chunks adjacents)
    context_window: int = 1
    # Modèle de reranking
    reranker_model: str = "BAAI/bge-reranker-base"
    # Activer le reranking par défaut
    use_reranking: bool = True
    # Activer la recherche hybride par défaut
    use_hybrid: bool = True
    # Activer le context expansion par défaut
    use_context_expansion: bool = True

    # === Robustness & Confidence ===
    # Seuil de confiance minimum (en dessous, on refuse de répondre)
    confidence_threshold: float = 0.25
    # Activer le filtrage PII dans les réponses
    enable_pii_filter: bool = True
    
    # === LLM ===
    # Modèle Ollama à utiliser
    llm_model: str = "qwen3:latest"
    # URL du serveur Ollama
    ollama_url: str = "http://localhost:11434"
    # Température (basse = plus factuel)
    temperature: float = 0.1
    # Top-p sampling
    top_p: float = 0.9
    # Tokens max en sortie
    max_tokens: int = 1024
    
    # === Utilisateur ===
    user_name: str = "Ismaël"
    
    def __post_init__(self):
        """Initialise les chemins dérivés."""
        if self.conversations_dir is None:
            self.conversations_dir = self.base_dir / "instagram_conversations"
        if self.index_dir is None:
            self.index_dir = self.base_dir / "rag_data"
        if self.vector_store_path is None:
            self.vector_store_path = self.index_dir / "faiss_index"
        if self.chunks_cache_path is None:
            self.chunks_cache_path = self.index_dir / "chunks.json"
        
        # Créer les dossiers nécessaires
        self.index_dir.mkdir(exist_ok=True)


# Instance par défaut
default_config = Config()
