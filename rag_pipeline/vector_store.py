"""
Vector Store basé sur FAISS pour le RAG Pipeline.
Stockage et recherche efficace d'embeddings.
"""
import json
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Set
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

    def add_vectors(
        self,
        new_chunks: List[Chunk],
        new_embeddings: np.ndarray
    ):
        """
        Add new vectors to the existing index (incremental update).

        Args:
            new_chunks: New chunks to add
            new_embeddings: Embeddings for new chunks (n_new, dim)
        """
        if self.index is None:
            # No existing index, create new one
            self.build_index(new_chunks, new_embeddings)
            return

        self._load_faiss()

        if len(new_chunks) != len(new_embeddings):
            raise ValueError(
                f"Number of chunks ({len(new_chunks)}) != "
                f"number of embeddings ({len(new_embeddings)})"
            )

        # Normalize new embeddings
        embeddings = new_embeddings.astype(np.float32)
        self._faiss.normalize_L2(embeddings)

        # Add to index
        self.index.add(embeddings)

        # Add chunks
        self.chunks.extend(new_chunks)

        print(f"Added {len(new_chunks)} vectors to index (total: {self.index.ntotal})")

    def remove_vectors(self, chunk_ids: List[str]) -> int:
        """
        Remove vectors by chunk ID (requires index rebuild).

        Note: FAISS IndexFlatIP doesn't support direct removal,
        so this rebuilds the index without the specified chunks.

        Args:
            chunk_ids: List of chunk IDs to remove

        Returns:
            Number of chunks actually removed
        """
        if self.index is None or not chunk_ids:
            return 0

        self._load_faiss()

        # Find indices to keep
        chunk_ids_set = set(chunk_ids)
        indices_to_keep = []
        new_chunks = []

        for i, chunk in enumerate(self.chunks):
            if chunk.chunk_id not in chunk_ids_set:
                indices_to_keep.append(i)
                new_chunks.append(chunk)

        removed_count = len(self.chunks) - len(new_chunks)

        if removed_count == 0:
            return 0

        # Reconstruct embeddings for kept indices
        # Note: This requires reconstructing vectors from FAISS
        dim = self.index.d
        kept_embeddings = np.zeros((len(indices_to_keep), dim), dtype=np.float32)

        for new_idx, old_idx in enumerate(indices_to_keep):
            kept_embeddings[new_idx] = self.index.reconstruct(old_idx)

        # Rebuild index
        self.index = self._faiss.IndexFlatIP(dim)
        self.index.add(kept_embeddings)
        self.chunks = new_chunks

        print(f"Removed {removed_count} vectors (remaining: {self.index.ntotal})")
        return removed_count

    def update_vectors(
        self,
        chunk_ids_to_remove: List[str],
        new_chunks: List[Chunk],
        new_embeddings: np.ndarray
    ) -> Tuple[int, int]:
        """
        Combined remove and add operation for efficient updates.

        Args:
            chunk_ids_to_remove: Chunk IDs to remove
            new_chunks: New chunks to add
            new_embeddings: Embeddings for new chunks

        Returns:
            Tuple of (removed_count, added_count)
        """
        if self.index is None:
            # No existing index
            self.build_index(new_chunks, new_embeddings)
            return 0, len(new_chunks)

        self._load_faiss()

        # Find indices to keep
        chunk_ids_set = set(chunk_ids_to_remove)
        indices_to_keep = []
        kept_chunks = []

        for i, chunk in enumerate(self.chunks):
            if chunk.chunk_id not in chunk_ids_set:
                indices_to_keep.append(i)
                kept_chunks.append(chunk)

        removed_count = len(self.chunks) - len(kept_chunks)

        # Reconstruct kept embeddings
        dim = self.index.d
        kept_embeddings = np.zeros((len(indices_to_keep), dim), dtype=np.float32)

        for new_idx, old_idx in enumerate(indices_to_keep):
            kept_embeddings[new_idx] = self.index.reconstruct(old_idx)

        # Normalize new embeddings
        new_emb = new_embeddings.astype(np.float32)
        self._faiss.normalize_L2(new_emb)

        # Combine kept and new
        if len(kept_embeddings) > 0 and len(new_emb) > 0:
            all_embeddings = np.vstack([kept_embeddings, new_emb])
        elif len(new_emb) > 0:
            all_embeddings = new_emb
        else:
            all_embeddings = kept_embeddings

        all_chunks = kept_chunks + list(new_chunks)

        # Rebuild index
        self.index = self._faiss.IndexFlatIP(dim)
        self.index.add(all_embeddings)
        self.chunks = all_chunks

        print(f"Updated index: removed {removed_count}, added {len(new_chunks)} (total: {self.index.ntotal})")
        return removed_count, len(new_chunks)

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Chunk]:
        """Find a chunk by its ID."""
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        return None

    def get_chunks_by_file(self, file_source: str) -> List[Chunk]:
        """Get all chunks from a specific file."""
        return [c for c in self.chunks if c.file_source == file_source]
