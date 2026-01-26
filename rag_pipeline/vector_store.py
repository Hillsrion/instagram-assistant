"""
Vector Store basé sur FAISS pour le RAG Pipeline.
Stockage et recherche efficace d'embeddings.
"""
import json
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

from .config import Config, default_config
from .chunker import Chunk


@dataclass
class SearchResult:
    """Résultat d'une recherche."""
    chunk: Chunk
    score: float
    rank: int


class VectorStore:
    """Store de vecteurs basé sur FAISS."""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.index = None
        self.chunks: List[Chunk] = []
        self._faiss = None
    
    def _load_faiss(self):
        """Charge FAISS (lazy loading)."""
        if self._faiss is not None:
            return
        
        try:
            import faiss
            self._faiss = faiss
        except ImportError:
            raise ImportError(
                "faiss est requis. "
                "Installez avec: pip install faiss-cpu"
            )
    
    def build_index(self, chunks: List[Chunk], embeddings: np.ndarray):
        """
        Construit l'index FAISS à partir des chunks et embeddings.
        
        Args:
            chunks: Liste des chunks
            embeddings: Matrice d'embeddings (n_chunks, dim)
        """
        self._load_faiss()
        
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Nombre de chunks ({len(chunks)}) != "
                f"nombre d'embeddings ({len(embeddings)})"
            )
        
        self.chunks = chunks
        dim = embeddings.shape[1]
        
        # Créer l'index FAISS avec Inner Product (équivalent cosine pour vecteurs normalisés)
        self.index = self._faiss.IndexFlatIP(dim)
        
        # Normaliser les embeddings (au cas où)
        embeddings = embeddings.astype(np.float32)
        self._faiss.normalize_L2(embeddings)
        
        # Ajouter les vecteurs
        self.index.add(embeddings)
        
        print(f"✅ Index FAISS créé avec {self.index.ntotal} vecteurs (dim={dim})")
    
    def search(
        self, 
        query_embedding: np.ndarray, 
        top_k: int = None,
        min_score: float = None
    ) -> List[SearchResult]:
        """
        Recherche les chunks les plus similaires.
        
        Args:
            query_embedding: Embedding de la requête
            top_k: Nombre de résultats à retourner
            min_score: Score minimum de similarité
            
        Returns:
            Liste de SearchResult triés par score décroissant
        """
        if self.index is None:
            raise RuntimeError("Index non initialisé. Appelez build_index() d'abord.")
        
        top_k = top_k or self.config.top_k
        min_score = min_score or self.config.min_similarity
        
        # Normaliser le vecteur de requête
        query = query_embedding.astype(np.float32).reshape(1, -1)
        self._faiss.normalize_L2(query)
        
        # Recherche
        scores, indices = self.index.search(query, top_k)
        
        results = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx < 0:  # Index invalide
                continue
            if score < min_score:
                continue
            
            results.append(SearchResult(
                chunk=self.chunks[idx],
                score=float(score),
                rank=rank + 1
            ))
        
        return results
    
    def save(self, path: Path = None):
        """Sauvegarde l'index et les métadonnées."""
        self._load_faiss()
        
        path = path or self.config.vector_store_path
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        # Sauvegarder l'index FAISS
        index_path = path / "index.faiss"
        self._faiss.write_index(self.index, str(index_path))
        
        # Sauvegarder les chunks (métadonnées)
        chunks_path = path / "chunks.json"
        chunks_data = [chunk.to_dict() for chunk in self.chunks]
        with open(chunks_path, 'w', encoding='utf-8') as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Index sauvegardé dans {path}")
    
    def load(self, path: Path = None) -> bool:
        """
        Charge l'index depuis le disque.
        
        Returns:
            True si chargement réussi, False sinon
        """
        self._load_faiss()
        
        path = path or self.config.vector_store_path
        path = Path(path)
        
        index_path = path / "index.faiss"
        chunks_path = path / "chunks.json"
        
        if not index_path.exists() or not chunks_path.exists():
            return False
        
        # Charger l'index FAISS
        self.index = self._faiss.read_index(str(index_path))
        
        # Charger les chunks
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        self.chunks = [Chunk.from_dict(d) for d in chunks_data]
        
        print(f"📂 Index chargé: {self.index.ntotal} vecteurs, {len(self.chunks)} chunks")
        return True
    
    @property
    def size(self) -> int:
        """Retourne le nombre de vecteurs dans l'index."""
        if self.index is None:
            return 0
        return self.index.ntotal
