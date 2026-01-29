"""
Tests for setup_indexes.py - Index construction.
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import Chunk


class TestBuildFaissIndex(unittest.TestCase):
    """Tests for build_faiss_index()."""

    def setUp(self):
        """Creates a temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        (self.temp_path / "rag_data").mkdir()

    def tearDown(self):
        """Cleans up the temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_faiss_index_no_embeddings(self):
        """build_faiss_index() returns False without embeddings."""
        import setup_indexes
        
        config = Config(
            base_dir=self.temp_path,
            index_dir=self.temp_path / "rag_data"
        )
        
        result = setup_indexes.build_faiss_index(config, [], None)
        self.assertFalse(result)

    def test_build_faiss_index_with_data(self):
        """build_faiss_index() builds index with valid data."""
        import setup_indexes
        
        config = Config(
            base_dir=self.temp_path,
            index_dir=self.temp_path / "rag_data"
        )
        
        # Create mock chunks
        chunks = [
            MagicMock(spec=Chunk, chunk_id=f"chunk_{i}")
            for i in range(3)
        ]
        
        # Create dummy embeddings
        embeddings = np.random.rand(3, 1024).astype(np.float32)
        
        # Mock VectorStore
        with patch('setup_indexes.VectorStore') as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store
            
            result = setup_indexes.build_faiss_index(config, chunks, embeddings)
            
            self.assertTrue(result)
            mock_store.build_index.assert_called_once()
            mock_store.save.assert_called_once()


class TestBuildBM25Index(unittest.TestCase):
    """Tests for build_bm25_index()."""

    def setUp(self):
        """Creates a temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        (self.temp_path / "rag_data").mkdir()

    def tearDown(self):
        """Cleans up the temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_bm25_index(self):
        """build_bm25_index() builds BM25 index."""
        import setup_indexes
        
        config = Config(
            base_dir=self.temp_path,
            index_dir=self.temp_path / "rag_data"
        )
        
        # Create mock chunks
        chunks = [
            MagicMock(spec=Chunk, chunk_id=f"chunk_{i}")
            for i in range(3)
        ]
        
        # Mock BM25Index
        with patch('setup_indexes.BM25Index') as MockBM25:
            mock_index = MagicMock()
            MockBM25.return_value = mock_index
            
            result = setup_indexes.build_bm25_index(config, chunks)
            
            self.assertTrue(result)
            mock_index.build_index.assert_called_once_with(chunks)
            mock_index.save.assert_called_once()


class TestBuildMetadataIndex(unittest.TestCase):
    """Tests for build_metadata_index()."""

    def setUp(self):
        """Creates a temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        (self.temp_path / "rag_data").mkdir()

    def tearDown(self):
        """Cleans up the temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_metadata_index(self):
        """build_metadata_index() builds SQLite index."""
        import setup_indexes
        
        config = Config(
            base_dir=self.temp_path,
            index_dir=self.temp_path / "rag_data"
        )
        
        # Create mock chunks
        chunks = [
            MagicMock(spec=Chunk, chunk_id=f"chunk_{i}")
            for i in range(3)
        ]
        
        # Mock MetadataStore
        with patch('setup_indexes.MetadataStore') as MockMetadata:
            mock_store = MagicMock()
            mock_store.get_all_participants.return_value = [("Alice", 10)]
            mock_store.get_date_range.return_value = ("2024-01-01", "2024-12-31")
            MockMetadata.return_value = mock_store
            
            result = setup_indexes.build_metadata_index(config, chunks)
            
            self.assertTrue(result)
            mock_store.build_index.assert_called_once_with(chunks)
            mock_store.close.assert_called_once()


class TestRunFunction(unittest.TestCase):
    """Tests for run() function."""

    def setUp(self):
        """Creates a temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        (self.temp_path / "rag_data").mkdir()

    def tearDown(self):
        """Cleans up the temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_run_no_chunks(self):
        """run() fails without chunks."""
        import setup_indexes
        
        config = Config(
            base_dir=self.temp_path,
            index_dir=self.temp_path / "rag_data"
        )
        
        result = setup_indexes.run(config)
        self.assertFalse(result)

    def test_run_only_bm25(self):
        """run() with only='bm25' builds only BM25."""
        import setup_indexes
        
        config = Config(
            base_dir=self.temp_path,
            index_dir=self.temp_path / "rag_data"
        )
        
        # Mock chunker to return chunks
        with patch('setup_indexes.ConversationChunker') as MockChunker:
            mock_chunker = MagicMock()
            mock_chunker.load_chunks.return_value = [MagicMock()]
            MockChunker.return_value = mock_chunker
            
            # Cache file must exist
            config.chunks_cache_path.parent.mkdir(parents=True, exist_ok=True)
            config.chunks_cache_path.write_text("{}")
            
            with patch('setup_indexes.BM25Index') as MockBM25:
                mock_bm25 = MagicMock()
                MockBM25.return_value = mock_bm25
                
                result = setup_indexes.run(config, only='bm25')
                
                # BM25 should be called
                mock_bm25.build_index.assert_called_once()


if __name__ == '__main__':
    unittest.main()