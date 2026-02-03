"""
Centralized RAG Pipeline Configuration.
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

@dataclass
class Config:
    """RAG Pipeline Configuration."""

    # === Paths ===
    base_dir: Path = field(default_factory=lambda: Path(os.getenv('BASE_DIR', Path(__file__).parent.parent)))
    conversations_dir: Path = field(default=None)
    index_dir: Path = field(default=None)
    vector_store_path: Path = field(default=None)
    chunks_cache_path: Path = field(default=None)
    
    # === Chunking ===
    # Max messages per chunk
    chunk_max_messages: int = field(default_factory=lambda: int(os.getenv('CHUNK_MAX_MESSAGES', '50')))
    # Max duration of a chunk in days (priority over max_messages)
    chunk_max_days: int = field(default_factory=lambda: int(os.getenv('CHUNK_MAX_DAYS', '3')))
    # Overlap between chunks (in messages)
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv('CHUNK_OVERLAP', '5')))
    # Gap (in hours) triggering a new chunk
    chunk_time_gap: float = field(default_factory=lambda: float(os.getenv('CHUNK_TIME_GAP', '6.0')))
    # Minimum messages per conversation (skip if fewer)
    min_messages_per_conversation: int = field(default_factory=lambda: int(os.getenv('MIN_MESSAGES_PER_CONVERSATION', '2')))
    # Skip conversations with deactivated accounts (utilisateurinstagram_*)
    skip_deactivated_accounts: bool = field(default_factory=lambda: os.getenv('SKIP_DEACTIVATED_ACCOUNTS', 'true').lower() == 'true')
    # Max hypothetical questions to generate/process per chunk
    max_questions: int = field(default_factory=lambda: int(os.getenv('MAX_QUESTIONS', '5')))

    # === Embeddings ===
    # Embedding model (bge-m3 recommended for multilingual)
    embedding_model: str = field(default_factory=lambda: os.getenv('EMBEDDING_MODEL', 'BAAI/bge-m3'))
    # Embedding dimension (1024 for bge-m3)
    embedding_dim: int = 1024
    # Use GPU if available
    use_gpu: bool = field(default_factory=lambda: os.getenv('USE_GPU', 'true').lower() == 'true')

    # === Retrieval ===
    # Number of chunks to retrieve
    top_k: int = field(default_factory=lambda: int(os.getenv('TOP_K', '12')))
    # Minimum similarity score (cosine)
    min_similarity: float = field(default_factory=lambda: float(os.getenv('MIN_SIMILARITY', '0.3')))

    # === Advanced Retrieval ===
    # Initial candidates for reranking
    initial_k: int = 50
    # Dense vs BM25 weight (0.5 = balanced)
    hybrid_alpha: float = 0.5
    # Context expansion window (adjacent chunks)
    context_window: int = 1
    # Reranking model
    reranker_model: str = "BAAI/bge-reranker-base"
    # Enable reranking by default
    use_reranking: bool = field(default_factory=lambda: os.getenv('USE_RERANKING', 'true').lower() == 'true')
    # Enable hybrid search by default
    use_hybrid: bool = field(default_factory=lambda: os.getenv('USE_HYBRID', 'true').lower() == 'true')
    # Enable context expansion by default
    use_context_expansion: bool = True

    # === Robustness & Confidence ===
    # Minimum confidence threshold (below this, refuse to answer)
    confidence_threshold: float = 0.25
    # Enable PII filtering in responses
    enable_pii_filter: bool = True

    # === Summary Index (Hierarchical Summaries) ===
    # Threshold to trigger fallback to summaries
    fallback_threshold: float = 0.35
    # Boost for summary results in final score
    summary_boost: float = 0.8
    
    # === LLM ===
    # Ollama models by performance tier (configurable via env)
    llm_model_fast: str = field(default_factory=lambda: os.getenv('LLM_MODEL_FAST', 'ministral-3:3b'))
    llm_model_strong: str = field(default_factory=lambda: os.getenv('LLM_MODEL_STRONG', 'ministral-3:14b'))
    # MLX models by performance tier (configurable via env)
    llm_model_mlx: str = field(default_factory=lambda: os.getenv('LLM_MODEL_MLX', 'mlx-community/granite-4.0-h-Tiny-4bit-DWQ'))
    llm_model_mlx_strong: str = field(default_factory=lambda: os.getenv('LLM_MODEL_MXL_STRONG', 'ministral-3:14b'))
    # Main LLM model (default = regular tier)
    llm_model: str = field(default_factory=lambda: os.getenv('LLM_MODEL', 'ministral-3:8b'))
    # Ollama server URL
    ollama_url: str = field(default_factory=lambda: os.getenv('OLLAMA_URL', 'http://localhost:11434'))
    # Temperature (low = more factual)
    temperature: float = 0.1
    # Top-p sampling
    top_p: float = 0.9
    # Max output tokens
    max_tokens: int = 1024
    # Ollama context window size (RAG + History)
    num_ctx: int = field(default_factory=lambda: int(os.getenv('LLM_NUM_CTX', '32768')))

    # === Complexity-Based Model Routing ===
    # Light model for simple chunks (faster)
    llm_light_model: str = field(default_factory=lambda: os.getenv('LLM_LIGHT_MODEL', 'ministral-3:3b'))
    # Loading strategy: "dual" (preload both), "on-demand" (load/unload), "batch" (group by complexity)
    model_loading_strategy: str = field(default_factory=lambda: os.getenv('MODEL_LOADING_STRATEGY', 'dual'))
    # Minimum RAM for dual-load strategy (GB)
    min_ram_gb_for_dual: float = 10.0
    # Complexity thresholds (0.0-1.0)
    # Complexity thresholds (0.0-1.0)
    complexity_simple_threshold: float = 0.28
    complexity_complex_threshold: float = 0.45
    # Route medium chunks to light model (3B) or strong model (8B)
    complexity_medium_uses_light: bool = True
    # Metric weights (must sum to 1.0)
    complexity_weights: dict = field(default_factory=lambda: {
        "participants": 0.20,
        "density": 0.25,
        "media": 0.15,
        "size": 0.15,
        "lexical_diversity": 0.15,
        "dialogue": 0.10,
    })
    # Force specific model (override complexity routing)
    force_model: Optional[str] = None
    # Enable/disable complexity routing
    enable_complexity_routing: bool = True

    # === User ===
    user_name: str = field(default_factory=lambda: os.getenv('USER_NAME', 'Ismaël'))
    
    def __post_init__(self):
        """Initializes derived paths and validates configuration."""
        # Convert base_dir to Path if string
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

        # Create necessary directories
        self.index_dir.mkdir(exist_ok=True)


# Default instance
default_config = Config()