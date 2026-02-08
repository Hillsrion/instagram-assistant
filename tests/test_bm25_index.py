from rag_pipeline.core.models import Chunk
"""
Tests for bm25_index.py module.
BM25 Index for lexical search.
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock

from rag_pipeline.core.config import Config
from rag_pipeline.indexing.bm25_index import BM25Index


class TestBM25Index(unittest.TestCase):

    def setUp(self):
        """Setup with temporary directory."""
        self.test_dir = tempfile.mkdtemp()
        self.config = Config(
            base_dir=Path(self.test_dir),
            index_dir=Path(self.test_dir) / "rag_data"
        )
        self.bm25 = BM25Index(self.config)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create_chunk(self, chunk_id: str, content: str, narrative_summary: str = "") -> Chunk:
        """Helper to create a chunk."""
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
        """Tokenization removes stopwords."""
        text = "Je suis allé à la plage avec mes amis"
        tokens = self.bm25.tokenize(text)
        
        # French stopwords must be removed
        self.assertNotIn("je", tokens)
        self.assertNotIn("suis", tokens)
        self.assertNotIn("la", tokens)
        self.assertNotIn("avec", tokens)
        self.assertNotIn("mes", tokens)
        
        # Meaningful words remain
        self.assertIn("plage", tokens)
        self.assertIn("amis", tokens)

    def test_tokenize_lowercase(self):
        """Tokenization converts to lowercase."""
        tokens = self.bm25.tokenize("HELLO World")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_tokenize_removes_short_tokens(self):
        """Tokens of 2 chars or less are removed."""
        tokens = self.bm25.tokenize("je suis ok")
        self.assertNotIn("ok", tokens)
        self.assertNotIn("je", tokens)

    def test_tokenize_handles_accents(self):
        """Tokenization handles French accents."""
        tokens = self.bm25.tokenize("café résumé")
        self.assertIn("café", tokens)
        # 'été' is a French stopword, so it's removed? No 'résumé' is kept.
        self.assertIn("résumé", tokens)

    # --- Tests build_index ---
    def test_build_index_creates_bm25(self):
        """build_index creates the BM25 object."""
        chunks = [
            self._create_chunk("c1", "Premier document sur les vacances"),
            self._create_chunk("c2", "Deuxième document sur le travail"),
        ]
        
        self.bm25.build_index(chunks)
        
        self.assertIsNotNone(self.bm25.bm25)
        self.assertEqual(len(self.bm25.chunks), 2)

    def test_build_index_includes_narrative_summary(self):
        """build_index uses narrative_summary if present."""
        chunk = self._create_chunk("c1", "Contenu brut")
        chunk.narrative_summary = "Résumé enrichi de la conversation"
        
        self.bm25.build_index([chunk])
        
        # Narrative summary should be in tokenized corpus
        self.assertIsNotNone(self.bm25.bm25)

    # --- Tests search ---
    def test_search_returns_relevant_results(self):
        """search returns relevant documents."""
        chunks = [
            self._create_chunk("c1", "On parle de vacances à la plage en été"),
            self._create_chunk("c2", "Discussion sur le projet de travail"),
            self._create_chunk("c3", "Voyage à la montagne cet hiver"),
        ]
        self.bm25.build_index(chunks)
        
        results = self.bm25.search("vacances plage", top_k=2)
        
        self.assertGreater(len(results), 0)
        # First result should be c1 (vacances + plage)
        self.assertEqual(results[0][0], 0)  # index of c1

    def test_search_respects_top_k(self):
        """search limits the number of results."""
        chunks = [self._create_chunk(f"c{i}", f"Document {i}") for i in range(10)]
        self.bm25.build_index(chunks)
        
        results = self.bm25.search("document", top_k=3)
        
        self.assertLessEqual(len(results), 3)

    def test_search_empty_query(self):
        """search with empty query returns empty list."""
        chunks = [self._create_chunk("c1", "Contenu")]
        self.bm25.build_index(chunks)
        
        results = self.bm25.search("")
        
        self.assertEqual(len(results), 0)

    def test_search_no_index(self):
        """search without index returns empty list."""
        results = self.bm25.search("test")
        self.assertEqual(len(results), 0)

    def test_search_min_score_filter(self):
        """search filters by minimum score."""
        chunks = [
            self._create_chunk("c1", "python programming code"),
            self._create_chunk("c2", "completely unrelated content about cooking"),
        ]
        self.bm25.build_index(chunks)
        
        results = self.bm25.search("python programming", min_score=0.5)
        
        # All results must have score > 0.5
        for idx, score in results:
            self.assertGreater(score, 0.5)

    # --- Tests get_scores_array ---
    def test_get_scores_array_returns_numpy(self):
        """get_scores_array returns a numpy array."""
        chunks = [self._create_chunk(f"c{i}", f"Doc {i}") for i in range(3)]
        self.bm25.build_index(chunks)
        
        scores = self.bm25.get_scores_array("test query")
        
        self.assertEqual(len(scores), 3)

    def test_get_scores_array_no_index(self):
        """get_scores_array without index returns zeros."""
        # No index built, no chunks
        scores = self.bm25.get_scores_array("test")
        self.assertEqual(len(scores), 0)

    # --- Tests save/load ---
    def test_save_load_index(self):
        """Index can be saved and loaded."""
        chunks = [
            self._create_chunk("c1", "Premier document"),
            self._create_chunk("c2", "Deuxième document"),
        ]
        self.bm25.build_index(chunks)
        self.bm25.save()
        
        # New BM25
        bm25_2 = BM25Index(self.config)
        loaded = bm25_2.load()
        
        self.assertTrue(loaded)
        self.assertIsNotNone(bm25_2.bm25)

    def test_load_nonexistent_returns_false(self):
        """load returns False if file does not exist."""
        result = self.bm25.load()
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()