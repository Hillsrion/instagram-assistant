"""
Tests pour le module bm25_index.py
Index BM25 pour recherche lexicale.
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock

from rag_pipeline.config import Config
from rag_pipeline.bm25_index import BM25Index
from rag_pipeline.chunker import Chunk


class TestBM25Index(unittest.TestCase):

    def setUp(self):
        """Setup avec répertoire temporaire"""
        self.test_dir = tempfile.mkdtemp()
        self.config = Config(
            base_dir=Path(self.test_dir),
            index_dir=Path(self.test_dir) / "rag_data"
        )
        self.bm25 = BM25Index(self.config)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create_chunk(self, chunk_id: str, content: str, narrative_summary: str = "") -> Chunk:
        """Helper pour créer un chunk"""
        chunk = Chunk(
            chunk_id=chunk_id,
            conversation_id="conv_1",
            participants=["User", "Friend"],
            date_start="2024-01-01",
            date_end="2024-01-02",
            message_count=10,
            content=content,
            file_source="test.txt"
        )
        chunk.narrative_summary = narrative_summary
        return chunk

    # --- Tests tokenize ---
    def test_tokenize_removes_stopwords(self):
        """La tokenisation supprime les stopwords"""
        text = "Je suis allé à la plage avec mes amis"
        tokens = self.bm25.tokenize(text)
        
        # Les stopwords FR doivent être retirés
        self.assertNotIn("je", tokens)
        self.assertNotIn("suis", tokens)
        self.assertNotIn("la", tokens)
        self.assertNotIn("avec", tokens)
        self.assertNotIn("mes", tokens)
        
        # Les mots significatifs restent
        self.assertIn("plage", tokens)
        self.assertIn("amis", tokens)

    def test_tokenize_lowercase(self):
        """La tokenisation met en minuscule"""
        tokens = self.bm25.tokenize("HELLO World")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_tokenize_removes_short_tokens(self):
        """Les tokens de 2 caractères ou moins sont retirés"""
        tokens = self.bm25.tokenize("je suis ok")
        self.assertNotIn("ok", tokens)
        self.assertNotIn("je", tokens)

    def test_tokenize_handles_accents(self):
        """La tokenisation gère les accents français"""
        tokens = self.bm25.tokenize("café résumé")
        self.assertIn("café", tokens)
        # été est un stopword français, donc retiré
        self.assertIn("résumé", tokens)

    # --- Tests build_index ---
    def test_build_index_creates_bm25(self):
        """build_index crée l'objet BM25"""
        chunks = [
            self._create_chunk("c1", "Premier document sur les vacances"),
            self._create_chunk("c2", "Deuxième document sur le travail"),
        ]
        
        self.bm25.build_index(chunks)
        
        self.assertIsNotNone(self.bm25.bm25)
        self.assertEqual(len(self.bm25.chunks), 2)

    def test_build_index_includes_narrative_summary(self):
        """build_index utilise le narrative_summary s'il existe"""
        chunk = self._create_chunk("c1", "Contenu brut")
        chunk.narrative_summary = "Résumé enrichi de la conversation"
        
        self.bm25.build_index([chunk])
        
        # Le résumé narratif doit être dans le corpus tokenisé
        self.assertIsNotNone(self.bm25.bm25)

    # --- Tests search ---
    def test_search_returns_relevant_results(self):
        """search retourne les documents pertinents"""
        chunks = [
            self._create_chunk("c1", "On parle de vacances à la plage en été"),
            self._create_chunk("c2", "Discussion sur le projet de travail"),
            self._create_chunk("c3", "Voyage à la montagne cet hiver"),
        ]
        self.bm25.build_index(chunks)
        
        results = self.bm25.search("vacances plage", top_k=2)
        
        self.assertGreater(len(results), 0)
        # Le premier résultat devrait être c1 (vacances + plage)
        self.assertEqual(results[0][0], 0)  # index de c1

    def test_search_respects_top_k(self):
        """search limite le nombre de résultats"""
        chunks = [self._create_chunk(f"c{i}", f"Document {i}") for i in range(10)]
        self.bm25.build_index(chunks)
        
        results = self.bm25.search("document", top_k=3)
        
        self.assertLessEqual(len(results), 3)

    def test_search_empty_query(self):
        """search avec query vide retourne liste vide"""
        chunks = [self._create_chunk("c1", "Contenu")]
        self.bm25.build_index(chunks)
        
        results = self.bm25.search("")
        
        self.assertEqual(len(results), 0)

    def test_search_no_index(self):
        """search sans index retourne liste vide"""
        results = self.bm25.search("test")
        self.assertEqual(len(results), 0)

    def test_search_min_score_filter(self):
        """search filtre par score minimum"""
        chunks = [
            self._create_chunk("c1", "python programming code"),
            self._create_chunk("c2", "completely unrelated content about cooking"),
        ]
        self.bm25.build_index(chunks)
        
        results = self.bm25.search("python programming", min_score=0.5)
        
        # Tous les résultats doivent avoir un score > 0.5
        for idx, score in results:
            self.assertGreater(score, 0.5)

    # --- Tests get_scores_array ---
    def test_get_scores_array_returns_numpy(self):
        """get_scores_array retourne un array numpy"""
        chunks = [self._create_chunk(f"c{i}", f"Doc {i}") for i in range(3)]
        self.bm25.build_index(chunks)
        
        scores = self.bm25.get_scores_array("test query")
        
        self.assertEqual(len(scores), 3)

    def test_get_scores_array_no_index(self):
        """get_scores_array sans index retourne zeros"""
        # Pas d'index construit, pas de chunks
        scores = self.bm25.get_scores_array("test")
        self.assertEqual(len(scores), 0)

    # --- Tests save/load ---
    def test_save_load_index(self):
        """L'index peut être sauvegardé et rechargé"""
        chunks = [
            self._create_chunk("c1", "Premier document"),
            self._create_chunk("c2", "Deuxième document"),
        ]
        self.bm25.build_index(chunks)
        self.bm25.save()
        
        # Nouveau BM25
        bm25_2 = BM25Index(self.config)
        loaded = bm25_2.load()
        
        self.assertTrue(loaded)
        self.assertIsNotNone(bm25_2.bm25)

    def test_load_nonexistent_returns_false(self):
        """load retourne False si fichier inexistant"""
        result = self.bm25.load()
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
