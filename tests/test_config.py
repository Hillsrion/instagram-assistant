"""
Tests pour le module config.py
Configuration centralisée du RAG Pipeline.
"""
import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from rag_pipeline.config import Config


class TestConfig(unittest.TestCase):

    def test_default_values(self):
        """Les valeurs par défaut sont correctement définies"""
        config = Config()
        # Chunking
        self.assertIsInstance(config.chunk_max_messages, int)
        self.assertIsInstance(config.chunk_time_gap, float)
        # Embeddings
        self.assertEqual(config.embedding_dim, 1024)
        # Retrieval
        self.assertIsInstance(config.top_k, int)
        self.assertIsInstance(config.min_similarity, float)
        # LLM
        self.assertIsInstance(config.llm_model, str)
        self.assertIsInstance(config.temperature, float)

    def test_post_init_creates_paths(self):
        """__post_init__ crée les chemins dérivés"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(base_dir=Path(tmpdir))
            
            # Vérifie que les chemins sont définis
            self.assertIsNotNone(config.conversations_dir)
            self.assertIsNotNone(config.index_dir)
            self.assertIsNotNone(config.vector_store_path)
            self.assertIsNotNone(config.chunks_cache_path)
            
            # Vérifie que index_dir est créé
            self.assertTrue(config.index_dir.exists())

    def test_post_init_with_string_paths(self):
        """__post_init__ convertit les strings en Path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(base_dir=tmpdir)  # String au lieu de Path
            self.assertIsInstance(config.base_dir, Path)

    def test_custom_paths_preserved(self):
        """Les chemins personnalisés sont préservés"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_conv_dir = Path(tmpdir) / "custom_conversations"
            custom_conv_dir.mkdir()
            
            config = Config(
                base_dir=Path(tmpdir),
                conversations_dir=custom_conv_dir
            )
            
            self.assertEqual(config.conversations_dir, custom_conv_dir)

    @patch.dict(os.environ, {'TOP_K': '10', 'MIN_SIMILARITY': '0.5'})
    def test_env_override(self):
        """Les variables d'environnement surchargent les valeurs par défaut"""
        config = Config()
        self.assertEqual(config.top_k, 10)
        self.assertEqual(config.min_similarity, 0.5)

    @patch.dict(os.environ, {'LLM_MODEL': 'test-model:latest'})
    def test_env_override_llm_model(self):
        """LLM_MODEL peut être surchargé par env"""
        config = Config()
        self.assertEqual(config.llm_model, 'test-model:latest')

    def test_embedding_model_default(self):
        """Le modèle d'embedding par défaut est bge-m3"""
        config = Config()
        self.assertIn('bge-m3', config.embedding_model)

    def test_ollama_url_default(self):
        """L'URL Ollama par défaut est localhost:11434"""
        config = Config()
        self.assertEqual(config.ollama_url, 'http://localhost:11434')


if __name__ == '__main__':
    unittest.main()
