"""
Module d'embeddings pour le RAG Pipeline.
Utilise sentence-transformers avec le modèle bge-m3 (multilingue).
"""
import numpy as np
from typing import List, Optional
from pathlib import Path

from .config import Config, default_config


class EmbeddingModel:
    """Génère des embeddings de haute qualité avec bge-m3."""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.model = None
        self._device = None
    
    def _load_model(self):
        """Charge le modèle d'embeddings (lazy loading)."""
        if self.model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
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
            self._device = "mps"  # Apple Silicon
        else:
            self._device = "cpu"
        
        print(f"📦 Chargement du modèle {self.config.embedding_model}...")
        print(f"🖥️  Device: {self._device}")
        
        self.model = SentenceTransformer(
            self.config.embedding_model,
            device=self._device
        )
        
        print("✅ Modèle chargé")
    
    def encode(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """
        Encode une liste de textes en embeddings.
        
        Args:
            texts: Liste de textes à encoder
            show_progress: Afficher une barre de progression
            
        Returns:
            Matrice numpy de shape (n_texts, embedding_dim)
        """
        self._load_model()
        
        embeddings = self.model.encode(
            texts,
            show_progress_bar=show_progress,
            normalize_embeddings=True,  # Normalisation pour cosine similarity
            batch_size=32,
        )
        
        return embeddings
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encode un seul texte."""
        return self.encode([text], show_progress=False)[0]
    
    @property
    def dimension(self) -> int:
        """Retourne la dimension des embeddings."""
        self._load_model()
        return self.model.get_sentence_embedding_dimension()


class OllamaEmbeddings:
    """
    Alternative: utilise Ollama pour les embeddings (nomic-embed-text).
    Plus lent mais ne nécessite pas sentence-transformers.
    """
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.model_name = "nomic-embed-text"
    
    def _call_ollama(self, text: str) -> List[float]:
        """Appelle l'API Ollama pour obtenir un embedding."""
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
        """Encode une liste de textes via Ollama."""
        embeddings = []
        
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
        
        return np.array(embeddings, dtype=np.float32)
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encode un seul texte."""
        return np.array(self._call_ollama(text), dtype=np.float32)
    
    @property
    def dimension(self) -> int:
        """Retourne la dimension des embeddings (768 pour nomic-embed-text)."""
        return 768
