"""
Index BM25 optimisé utilisant rank_bm25.
Permet la recherche par mots-clés rapide et efficace.
"""
import re
import pickle
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Set
from rank_bm25 import BM25Okapi

from .config import Config, default_config
from .chunker import Chunk


class BM25Index:
    """
    Index BM25 pour recherche lexicale (optimisé avec rank_bm25).

    BM25 est excellent pour:
    - Mots-clés exacts (noms propres, termes techniques)
    - Requêtes courtes
    - Compléter la recherche sémantique
    """

    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.chunks: List[Chunk] = []
        self.bm25: Optional[BM25Okapi] = None
        
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
        
        print(f"📚 Construction de l'index BM25 ({len(chunks)} chunks)...")

        # Tokenizer tous les documents
        tokenized_corpus = []
        for chunk in chunks:
            # On indexe le contenu complet
            text_parts = [chunk.content]
            if chunk.narrative_summary:
                text_parts.insert(0, chunk.narrative_summary)
            text = " ".join(text_parts)
            tokenized_corpus.append(self.tokenize(text))

        # Initialisation de BM25Okapi
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        print(f"✅ Index BM25 construit")

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
        if self.bm25 is None:
            return []

        tokenized_query = self.tokenize(query)
        if not tokenized_query:
            return []

        # Obtenir les scores pour tout le corpus
        scores = self.bm25.get_scores(tokenized_query)
        
        # Filtrer et trier
        doc_scores = []
        for idx, score in enumerate(scores):
            if score > min_score:
                doc_scores.append((idx, score))

        # Trier par score décroissant
        doc_scores.sort(key=lambda x: x[1], reverse=True)

        return doc_scores[:top_k]

    def get_scores_array(self, query: str) -> np.ndarray:
        """
        Retourne les scores BM25 pour tous les documents.

        Utile pour la fusion avec les scores dense.
        """
        if self.bm25 is None:
            return np.zeros(len(self.chunks))

        tokenized_query = self.tokenize(query)
        if not tokenized_query:
            return np.zeros(len(self.chunks))

        scores = self.bm25.get_scores(tokenized_query)
        return np.array(scores)

    def save(self, path: Path = None):
        """Sauvegarde l'index BM25."""
        path = path or (self.config.index_dir / "bm25_index.pkl")

        if self.bm25 is None:
            print("⚠️ Aucun index à sauvegarder")
            return

        data = {
            'bm25': self.bm25,
            # On ne sauvegarde pas les chunks ici pour éviter la duplication
            # (ils sont gérés par le vector store ou un chunk store central)
            # Mais on doit s'assurer que l'ordre reste le même.
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

        self.bm25 = data.get('bm25')
        
        # Note: self.chunks doit être re-assigné après chargement par l'orchestrateur
        # car on ne le sauvegarde pas dans le pickle pour économiser l'espace
        
        if self.bm25:
            print(f"📂 Index BM25 chargé")
            return True
        return False
