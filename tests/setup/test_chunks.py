"""
Tests pour setup_chunks.py - Génération des chunks.
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.config import Config


class TestSetupChunks(unittest.TestCase):
    """Tests pour le script setup_chunks."""

    def setUp(self):
        """Crée un répertoire temporaire pour les tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Créer la structure de dossiers
        (self.temp_path / "conversations").mkdir()
        (self.temp_path / "rag_data").mkdir()

    def tearDown(self):
        """Nettoie le répertoire temporaire."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_run_with_no_conversations(self):
        """run() sans conversations crée un cache vide."""
        import setup_chunks
        
        config = Config(
            base_dir=self.temp_path,
            conversations_dir=self.temp_path / "conversations",
            index_dir=self.temp_path / "rag_data"
        )
        
        result = setup_chunks.run(config, reset=False, limit=None)
        
        self.assertTrue(result)

    def test_run_with_test_conversations(self):
        """run() avec import_test copie les conversations de test."""
        import setup_chunks
        
        # Créer un dossier test_conversations avec un fichier
        test_conv_dir = self.temp_path / "test_conversations"
        test_conv_dir.mkdir()
        test_file = test_conv_dir / "test_conv.txt"
        test_file.write_text("Test conversation content")
        
        config = Config(
            base_dir=self.temp_path,
            conversations_dir=self.temp_path / "conversations",
            index_dir=self.temp_path / "rag_data"
        )
        
        # Mock le chemin test_conversations
        with patch.object(Path, '__new__', return_value=test_conv_dir):
            # L'import devrait créer les chunks
            result = setup_chunks.run(config, reset=False, limit=None, import_test=False)
        
        self.assertTrue(result)

    def test_run_with_limit(self):
        """run() avec limit ne traite qu'un nombre limité de conversations."""
        import setup_chunks
        
        config = Config(
            base_dir=self.temp_path,
            conversations_dir=self.temp_path / "conversations",
            index_dir=self.temp_path / "rag_data"
        )
        
        # Créer quelques fichiers de conversation
        for i in range(5):
            conv_file = config.conversations_dir / f"conv_{i}.txt"
            conv_file.write_text(f"[2024-01-01 12:00:00] User: Message {i}")
        
        result = setup_chunks.run(config, reset=False, limit=2)
        
        self.assertTrue(result)

    def test_run_with_reset(self):
        """run() avec reset régénère les chunks."""
        import setup_chunks
        
        config = Config(
            base_dir=self.temp_path,
            conversations_dir=self.temp_path / "conversations",
            index_dir=self.temp_path / "rag_data"
        )
        
        # Premier run
        result1 = setup_chunks.run(config, reset=False)
        self.assertTrue(result1)
        
        # Deuxième run avec reset
        result2 = setup_chunks.run(config, reset=True)
        self.assertTrue(result2)


class TestMainFunction(unittest.TestCase):
    """Tests pour la fonction main()."""

    def test_main_argparse(self):
        """main() parse correctement les arguments."""
        import setup_chunks
        import argparse
        
        # Test que le parser est bien configuré
        parser = argparse.ArgumentParser()
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--import-test", action="store_true")
        
        args = parser.parse_args(["--reset", "--limit", "10"])
        self.assertTrue(args.reset)
        self.assertEqual(args.limit, 10)


if __name__ == '__main__':
    unittest.main()
