"""
Index BM25 pour recherche par mots-clés (sparse search).
Permet de combiner avec la recherche dense pour un hybrid search.
"""
import re
import json
import pickle
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Set
from collections import defaultdict

from .config import Config, default_config
from .chunker import Chunk


class BM25Index:
    """
    Index BM25 pour recherche lexicale.

    BM25 est excellent pour:
    - Mots-clés exacts (noms propres, termes techniques)
    - Requêtes courtes
    - Compléter la recherche sémantique
    """

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.chunks: List[Chunk] = []
        self.tokenized_docs: List[List[str]] = []
        self.doc_freqs: defaultdict = defaultdict(int)
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0.0
        self.idf: dict = {}

        # Paramètres BM25
        self.k1 = 1.5  # Saturation term frequency
        self.b = 0.75  # Length normalization

        # Stopwords français/anglais
        self.stopwords = self._load_stopwords()

    def _load_stopwords(self) -> Set[str]:
        """Charge les stopwords FR/EN."""
        return {
            # Français
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

            # Anglais
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

            # Communs chat
            'haha', 'hahaha', 'lol', 'mdr', 'ptdr', 'ok', 'okay', 'oui', 'non', 'yes', 'no',
            'merci', 'thanks', 'please', 'svp', 'stp',
        }

    def tokenize(self, text: str) -> List[str]:
        """Tokenize et nettoie un texte."""
        # Lowercase et extraction des mots
        text = text.lower()
        tokens = re.findall(r'\b[a-zA-ZÀ-ÿ]{2,}\b', text)

        # Filtrer stopwords et tokens trop courts
        tokens = [t for t in tokens if t not in self.stopwords and len(t) > 2]

        return tokens

    def build_index(self, chunks: List[Chunk]):
        """
        Construit l'index BM25 à partir des chunks.

        Args:
            chunks: Liste des chunks à indexer
        """
        self.chunks = chunks
        self.tokenized_docs = []
        self.doc_freqs = defaultdict(int)
        self.doc_lengths = []

        print(f"📚 Construction de l'index BM25 ({len(chunks)} chunks)...")

        # Tokenizer tous les documents
        for chunk in chunks:
            # On indexe le contenu complet (pas juste le résumé)
            text = f"{chunk.summary} {chunk.content}"
            tokens = self.tokenize(text)
            self.tokenized_docs.append(tokens)
            self.doc_lengths.append(len(tokens))

            # Compter les document frequencies
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] += 1

        # Calculer la longueur moyenne
        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0

        # Calculer IDF pour tous les termes
        n_docs = len(chunks)
        for term, df in self.doc_freqs.items():
            # IDF avec smoothing
            self.idf[term] = np.log((n_docs - df + 0.5) / (df + 0.5) + 1)

        print(f"✅ Index BM25 construit: {len(self.doc_freqs)} termes uniques")

    def _score_document(self, query_tokens: List[str], doc_idx: int) -> float:
        """Calcule le score BM25 pour un document."""
        doc_tokens = self.tokenized_docs[doc_idx]
        doc_length = self.doc_lengths[doc_idx]

        # Compter les term frequencies dans le document
        tf = defaultdict(int)
        for token in doc_tokens:
            tf[token] += 1

        score = 0.0
        for term in query_tokens:
            if term not in self.idf:
                continue

            term_freq = tf.get(term, 0)
            if term_freq == 0:
                continue

            idf = self.idf[term]

            # BM25 formula
            numerator = term_freq * (self.k1 + 1)
            denominator = term_freq + self.k1 * (1 - self.b + self.b * doc_length / self.avg_doc_length)
            score += idf * (numerator / denominator)

        return score

    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0
    ) -> List[Tuple[int, float]]:
        """
        Recherche BM25.

        Args:
            query: Requête textuelle
            top_k: Nombre de résultats
            min_score: Score minimum

        Returns:
            Liste de (doc_idx, score) triés par score
        """
        query_tokens = self.tokenize(query)

        if not query_tokens:
            return []

        # Calculer les scores pour tous les documents
        scores = []
        for doc_idx in range(len(self.chunks)):
            score = self._score_document(query_tokens, doc_idx)
            if score > min_score:
                scores.append((doc_idx, score))

        # Trier par score décroissant
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores[:top_k]

    def get_scores_array(self, query: str) -> np.ndarray:
        """
        Retourne les scores BM25 pour tous les documents.

        Utile pour la fusion avec les scores dense.
        """
        query_tokens = self.tokenize(query)

        if not query_tokens:
            return np.zeros(len(self.chunks))

        scores = np.array([
            self._score_document(query_tokens, i)
            for i in range(len(self.chunks))
        ])

        return scores

    def save(self, path: Path = None):
        """Sauvegarde l'index BM25."""
        path = path or (self.config.index_dir / "bm25_index.pkl")

        data = {
            'tokenized_docs': self.tokenized_docs,
            'doc_freqs': dict(self.doc_freqs),
            'doc_lengths': self.doc_lengths,
            'avg_doc_length': self.avg_doc_length,
            'idf': self.idf,
            'k1': self.k1,
            'b': self.b,
        }

        with open(path, 'wb') as f:
            pickle.dump(data, f)

        print(f"💾 Index BM25 sauvegardé dans {path}")

    def load(self, path: Path = None) -> bool:
        """Charge l'index BM25."""
        path = path or (self.config.index_dir / "bm25_index.pkl")

        if not path.exists():
            return False

        with open(path, 'rb') as f:
            data = pickle.load(f)

        self.tokenized_docs = data['tokenized_docs']
        self.doc_freqs = defaultdict(int, data['doc_freqs'])
        self.doc_lengths = data['doc_lengths']
        self.avg_doc_length = data['avg_doc_length']
        self.idf = data['idf']
        self.k1 = data.get('k1', 1.5)
        self.b = data.get('b', 0.75)

        print(f"📂 Index BM25 chargé: {len(self.tokenized_docs)} docs, {len(self.idf)} termes")
        return True
