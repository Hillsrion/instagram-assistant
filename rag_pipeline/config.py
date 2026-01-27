"""
Configuration centralisée du RAG Pipeline.
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

@dataclass
class Config:
    """Configuration du pipeline RAG."""

    # === Chemins ===
    base_dir: Path = field(default_factory=lambda: Path(os.getenv('BASE_DIR', Path(__file__).parent.parent)))
    conversations_dir: Path = field(default=None)
    index_dir: Path = field(default=None)
    vector_store_path: Path = field(default=None)
    chunks_cache_path: Path = field(default=None)
    
    # === Chunking ===
    # Nombre max de messages par chunk
    chunk_max_messages: int = field(default_factory=lambda: int(os.getenv('CHUNK_MAX_MESSAGES', '50')))
    # Durée max d'un chunk en jours (prioritaire sur max_messages)
    chunk_max_days: int = field(default_factory=lambda: int(os.getenv('CHUNK_MAX_DAYS', '3')))
    # Chevauchement entre chunks (en messages)
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv('CHUNK_OVERLAP', '5')))

    # === Embeddings ===
    # Modèle d'embeddings (bge-m3 recommandé pour multilingue)
    embedding_model: str = field(default_factory=lambda: os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3'))
    # Dimension des embeddings (1024 pour bge-m3)
    embedding_dim: int = 1024
    # Utiliser GPU si disponible
    use_gpu: bool = field(default_factory=lambda: os.getenv('USE_GPU', 'true').lower() == 'true')

    # === Retrieval ===
    # Nombre de chunks à récupérer
    top_k: int = field(default_factory=lambda: int(os.getenv('TOP_K', '5')))
    # Score minimum de similarité (cosine)
    min_similarity: float = field(default_factory=lambda: float(os.getenv('MIN_SIMILARITY', '0.3')))

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
    use_reranking: bool = field(default_factory=lambda: os.getenv('USE_RERANKING', 'true').lower() == 'true')
    # Activer la recherche hybride par défaut
    use_hybrid: bool = field(default_factory=lambda: os.getenv('USE_HYBRID', 'true').lower() == 'true')
    # Activer le context expansion par défaut
    use_context_expansion: bool = True

    # === Robustness & Confidence ===
    # Seuil de confiance minimum (en dessous, on refuse de répondre)
    confidence_threshold: float = 0.25
    # Activer le filtrage PII dans les réponses
    enable_pii_filter: bool = True
    
    # === LLM ===
    # Modèle Ollama à utiliser
    llm_model: str = field(default_factory=lambda: os.getenv('LLM_MODEL', 'qwen3:latest'))
    # URL du serveur Ollama
    ollama_url: str = field(default_factory=lambda: os.getenv('OLLAMA_URL', 'http://localhost:11434'))
    # Température (basse = plus factuel)
    temperature: float = 0.1
    # Top-p sampling
    top_p: float = 0.9
    # Tokens max en sortie
    max_tokens: int = 1024

    # === Utilisateur ===
    user_name: str = field(default_factory=lambda: os.getenv('USER_NAME', 'Ismaël'))
    
    def __post_init__(self):
        """Initialise les chemins dérivés."""
        # Convertir base_dir en Path si c'est une string
        if isinstance(self.base_dir, str):
            self.base_dir = Path(self.base_dir)

        if self.conversations_dir is None:
            conv_dir = os.getenv('CONVERSATIONS_DIR', 'instagram_conversations')
            self.conversations_dir = self.base_dir / conv_dir if not Path(conv_dir).is_absolute() else Path(conv_dir)
        elif isinstance(self.conversations_dir, str):
            self.conversations_dir = Path(self.conversations_dir)

        if self.index_dir is None:
            idx_dir = os.getenv('INDEX_DIR', 'rag_data')
            self.index_dir = self.base_dir / idx_dir if not Path(idx_dir).is_absolute() else Path(idx_dir)
        elif isinstance(self.index_dir, str):
            self.index_dir = Path(self.index_dir)

        if self.vector_store_path is None:
            self.vector_store_path = self.index_dir / "faiss_index"
        elif isinstance(self.vector_store_path, str):
            self.vector_store_path = Path(self.vector_store_path)

        if self.chunks_cache_path is None:
            self.chunks_cache_path = self.index_dir / "chunks.json"
        elif isinstance(self.chunks_cache_path, str):
            self.chunks_cache_path = Path(self.chunks_cache_path)

        # Créer les dossiers nécessaires
        self.index_dir.mkdir(exist_ok=True)


# Instance par défaut
default_config = Config()
