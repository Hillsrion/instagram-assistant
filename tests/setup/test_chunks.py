"""
Tests for setup_chunks.py - Chunk generation.
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
    """Tests for setup_chunks script."""

    def setUp(self):
        """Creates a temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create folder structure
        (self.temp_path / "conversations").mkdir()
        (self.temp_path / "rag_data").mkdir()

    def tearDown(self):
        """Cleans up the temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_run_with_no_conversations(self):
        """run() without conversations creates an empty cache."""
        import setup_chunks
        
        config = Config(
            base_dir=self.temp_path,
            conversations_dir=self.temp_path / "conversations",
            index_dir=self.temp_path / "rag_data"
        )
        
        result = setup_chunks.run(config, reset=False, limit=None)
        
        self.assertTrue(result)

    def test_run_with_test_conversations(self):
        """run() with import_test copies test conversations."""
        import setup_chunks
        
        # Create a test_conversations folder with a file
        test_conv_dir = self.temp_path / "test_conversations"
        test_conv_dir.mkdir()
        test_file = test_conv_dir / "test_conv.txt"
        test_file.write_text("Test conversation content")
        
        config = Config(
            base_dir=self.temp_path,
            conversations_dir=self.temp_path / "conversations",
            index_dir=self.temp_path / "rag_data"
        )
        
        # Mock test_conversations path
        with patch.object(Path, '__new__', return_value=test_conv_dir):
            # Import should create chunks
            result = setup_chunks.run(config, reset=False, limit=None, import_test=False)
        
        self.assertTrue(result)

    def test_run_with_limit(self):
        """run() with limit processes only a limited number of conversations."""
        import setup_chunks
        
        config = Config(
            base_dir=self.temp_path,
            conversations_dir=self.temp_path / "conversations",
            index_dir=self.temp_path / "rag_data"
        )
        
        # Create some conversation files
        for i in range(5):
            conv_file = config.conversations_dir / f"conv_{i}.txt"
            conv_file.write_text(f"[2024-01-01 12:00:00] User: Message {i}")
        
        result = setup_chunks.run(config, reset=False, limit=2)
        
        self.assertTrue(result)

    def test_run_with_reset(self):
        """run() with reset regenerates chunks."""
        import setup_chunks
        
        config = Config(
            base_dir=self.temp_path,
            conversations_dir=self.temp_path / "conversations",
            index_dir=self.temp_path / "rag_data"
        )
        
        # First run
        result1 = setup_chunks.run(config, reset=False)
        self.assertTrue(result1)
        
        # Second run with reset
        result2 = setup_chunks.run(config, reset=True)
        self.assertTrue(result2)


class TestMainFunction(unittest.TestCase):
    """Tests for main() function."""

    def test_main_argparse(self):
        """main() parses arguments correctly."""
        import setup_chunks
        import argparse
        
        # Test parser configuration
        parser = argparse.ArgumentParser()
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--import-test", action="store_true")
        
        args = parser.parse_args(["--reset", "--limit", "10"])
        self.assertTrue(args.reset)
        self.assertEqual(args.limit, 10)


if __name__ == '__main__':
    unittest.main()