"""
Embeddings module for RAG Pipeline.
Uses sentence-transformers with bge-m3 model (multilingual).
"""
import numpy as np
import time
from typing import List, Optional
from pathlib import Path

from .config import Config, default_config
from .embedding_log import EmbeddingLogger


class EmbeddingModel:
    """Generates high-quality embeddings with bge-m3."""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.model = None
        self._device = None
        self.logger = EmbeddingLogger()
    
    def _load_model(self):
        """Loads the embedding model (lazy loading)."""
        if self.model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            import torch
        except ImportError:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            )
        
        # Determine device
        if self.config.use_gpu and torch.cuda.is_available():
            self._device = "cuda"
        elif self.config.use_gpu and torch.backends.mps.is_available():
            self._device = "mps"  # Apple Silicon
        else:
            self._device = "cpu"
        
        print(f"📦 Loading model {self.config.embedding_model}...")
        print(f"🖥️  Device: {self._device}")
        
        self.model = SentenceTransformer(
            self.config.embedding_model,
            device=self._device
        )
        
        print("✅ Model loaded")
    
    def encode(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """
        Encodes a list of texts into embeddings.
        
        Args:
            texts: List of texts to encode
            show_progress: Show progress bar
            
        Returns:
            Numpy matrix of shape (n_texts, embedding_dim)
        """
        self._load_model()
        
        start_time = time.time()
        batch_size = 32
        
        embeddings = self.model.encode(
            texts,
            show_progress_bar=show_progress,
            normalize_embeddings=True,  # Normalization for cosine similarity
            batch_size=batch_size,
        )
        
        duration_ms = (time.time() - start_time) * 1000
        self.logger.log_batch(
            batch_size=batch_size,
            total_texts=len(texts),
            model_name=self.config.embedding_model,
            device=str(self._device),
            duration_ms=duration_ms
        )
        
        return embeddings
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encodes a single text."""
        return self.encode([text], show_progress=False)[0]
    
    @property
    def dimension(self) -> int:
        """Returns the embedding dimension."""
        self._load_model()
        return self.model.get_sentence_embedding_dimension()


class OllamaEmbeddings:
    """
    Alternative: uses Ollama for embeddings (nomic-embed-text).
    Slower but does not require sentence-transformers.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.model_name = "nomic-embed-text"
        self.logger = EmbeddingLogger()
    
    def _call_ollama(self, text: str) -> List[float]:
        """Calls Ollama API to get an embedding."""
        import requests
        
        response = requests.post(
            f"{self.config.ollama_url}/api/embeddings",
            json={
                "model": self.model_name,
                "prompt": text
            }
        )
        response.raise_for_status()
        return response.json()["embedding"]
    
    def encode(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """Encodes a list of texts via Ollama."""
        embeddings = []
        
        start_time = time.time()
        iterator = texts
        if show_progress:
            try:
                from tqdm import tqdm
                iterator = tqdm(texts, desc="Embedding")
            except ImportError:
                pass
        
        for text in iterator:
            emb = self._call_ollama(text)
            embeddings.append(emb)
        
        duration_ms = (time.time() - start_time) * 1000
        self.logger.log_batch(
            batch_size=1,  # Ollama is usually sequential in this implementation
            total_texts=len(texts),
            model_name=self.model_name,
            device="ollama_api",
            duration_ms=duration_ms
        )
        
        return np.array(embeddings, dtype=np.float32)
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encodes a single text."""
        return np.array(self._call_ollama(text), dtype=np.float32)
    
    @property
    def dimension(self) -> int:
        """Returns the embedding dimension (768 for nomic-embed-text)."""
        return 768