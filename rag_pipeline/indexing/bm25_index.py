"""
Optimized BM25 index using rank_bm25.
Enables fast and efficient keyword search.
"""
import re
import pickle
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Set
from rank_bm25 import BM25Okapi

from rag_pipeline.core.config import Config, default_config
from rag_pipeline.core.models import Chunk


class BM25Index:
    """
    BM25 Index for lexical search (optimized with rank_bm25).

    BM25 is excellent for:
    - Exact keywords (proper names, technical terms)
    - Short queries
    - Complementing semantic search
    """

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.chunks: List[Chunk] = []
        self.bm25: Optional[BM25Okapi] = None
        
        # French/English stopwords
        self.stopwords = self._load_stopwords()

    def _load_stopwords(self) -> Set[str]:
        """Loads FR/EN stopwords."""
        return {
            # French
            'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'et', 'en', 'au', 'aux',
            'ce', 'ces', 'cet', 'cette', 'qui', 'que', 'quoi', 'dont', 'où',
            'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles',
            'me', 'te', 'se', 'lui', 'leur', 'moi', 'toi', 'soi',
            'mon', 'ma', 'mes', 'ton', 'ta', 'tes', 'son', 'sa', 'ses',
            'notre', 'votre', 'nos', 'vos', 'leurs',
            'ne', 'pas', 'plus', 'mais', 'ou', 'donc', 'car', 'si',
            'pour', 'par', 'avec', 'sans', 'dans', 'sur', 'sous', 'entre',
            'avoir', 'être', 'faire', 'aller', 'voir', 'dire', 'venir',
            'est', 'sont', 'était', 'été', 'suis', 'es', 'sommes', 'êtes',
            'ai', 'as', 'avons', 'avez', 'ont', 'fait', 'dit',
            'tout', 'tous', 'toute', 'toutes', 'même', 'aussi', 'très',
            'bien', 'peu', 'trop', 'plus', 'moins', 'encore', 'toujours', 'jamais',
            'alors', 'donc', 'ainsi', 'comme', 'quand', 'comment', 'pourquoi',
            'ça', 'cela', 'celui', 'celle', 'ceux', 'celles',

            # English
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
            'my', 'your', 'his', 'its', 'our', 'their',
            'this', 'that', 'these', 'those', 'what', 'which', 'who', 'whom', 'whose',
            'when', 'where', 'why', 'how',
            'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some', 'any',
            'no', 'not', 'only', 'same', 'so', 'than', 'too', 'very', 'just',

            # Chat commons
            'haha', 'hahaha', 'lol', 'mdr', 'ptdr', 'ok', 'okay', 'oui', 'non', 'yes', 'no',
            'merci', 'thanks', 'please', 'svp', 'stp',
        }

    def tokenize(self, text: str) -> List[str]:
        """Tokenize and clean text."""
        # Lowercase and word extraction
        text = text.lower()
        tokens = re.findall(r'\b[a-zA-ZÀ-ÿ]{2,}\b', text)

        # Filter stopwords and short tokens
        tokens = [t for t in tokens if t not in self.stopwords and len(t) > 2]

        return tokens

    def build_index(self, chunks: List[Chunk]):
        """
        Builds BM25 index from chunks.

        Args:
            chunks: List of chunks to index
        """
        self.chunks = chunks
        
        print(f"📚 Building BM25 index ({len(chunks)} chunks)...")

        # Tokenize all documents
        tokenized_corpus = []
        for chunk in chunks:
            # Index complete content
            text_parts = [chunk.content]
            if chunk.narrative_summary:
                text_parts.insert(0, chunk.narrative_summary)
            text = " ".join(text_parts)
            tokenized_corpus.append(self.tokenize(text))

        # Initialize BM25Okapi
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        print(f"✅ BM25 index built")

    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0
    ) -> List[Tuple[int, float]]:
        """
        BM25 Search.

        Args:
            query: Text query
            top_k: Number of results
            min_score: Minimum score

        Returns:
            List of (doc_idx, score) sorted by score
        """
        if self.bm25 is None:
            return []

        tokenized_query = self.tokenize(query)
        if not tokenized_query:
            return []

        # Get scores for corpus
        scores = self.bm25.get_scores(tokenized_query)
        
        # Filter and sort
        doc_scores = []
        for idx, score in enumerate(scores):
            if score > min_score:
                doc_scores.append((idx, score))

        # Sort by score desc
        doc_scores.sort(key=lambda x: x[1], reverse=True)

        return doc_scores[:top_k]

    def get_scores_array(self, query: str) -> np.ndarray:
        """
        Returns BM25 scores for all documents.

        Useful for fusion with dense scores.
        """
        if self.bm25 is None:
            return np.zeros(len(self.chunks))

        tokenized_query = self.tokenize(query)
        if not tokenized_query:
            return np.zeros(len(self.chunks))

        scores = self.bm25.get_scores(tokenized_query)
        return np.array(scores)

    def save(self, path: Path = None):
        """Saves the BM25 index."""
        path = path or (self.config.index_dir / "bm25_index.pkl")

        if self.bm25 is None:
            print("⚠️ No index to save")
            return

        data = {
            'bm25': self.bm25,
            # We don't save chunks here to avoid duplication
            # (they are managed by vector store or central chunk store)
            # But we must ensure order remains the same.
        }

        with open(path, 'wb') as f:
            pickle.dump(data, f)

        print(f"💾 BM25 index saved to {path}")

    def load(self, path: Path = None) -> bool:
        """Loads the BM25 index."""
        path = path or (self.config.index_dir / "bm25_index.pkl")

        if not path.exists():
            return False

        with open(path, 'rb') as f:
            data = pickle.load(f)

        self.bm25 = data.get('bm25')
        
        # Note: self.chunks must be re-assigned after loading by the orchestrator
        # because we don't save it in pickle to save space
        
        if self.bm25:
            print(f"📂 BM25 index loaded")
            return True
        return False