"""
Tests for delta_tracker.py module.
File change tracking for incremental indexing.
"""
import unittest
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime

from rag_pipeline.core.config import Config
from rag_pipeline.indexing.delta_tracker import DeltaTracker, FileState, DeltaResult


class TestDeltaTracker(unittest.TestCase):

    def setUp(self):
        """Create temporary directory."""
        self.test_dir = tempfile.mkdtemp()
        self.conv_dir = Path(self.test_dir) / "conversations"
        self.conv_dir.mkdir()
        self.index_dir = Path(self.test_dir) / "rag_data"
        self.index_dir.mkdir()
        
        self.config = Config(
            base_dir=Path(self.test_dir),
            conversations_dir=self.conv_dir,
            index_dir=self.index_dir
        )
        
        self.tracker = DeltaTracker(self.config)

    def tearDown(self):
        """Cleanup temporary directory."""
        shutil.rmtree(self.test_dir)

    def _create_file(self, filename: str, content: str = "test content") -> Path:
        """Helper to create a file."""
        filepath = self.conv_dir / filename
        filepath.write_text(content, encoding='utf-8')
        return filepath

    # --- Tests compute_hash ---
    def test_compute_hash_consistent(self):
        """Hash is consistent for same content."""
        file1 = self._create_file("test1.txt", "Hello World")
        hash1 = self.tracker.compute_hash(file1)
        hash2 = self.tracker.compute_hash(file1)
        self.assertEqual(hash1, hash2)

    def test_compute_hash_different_content(self):
        """Hash changes with content."""
        file1 = self._create_file("test1.txt", "Hello")
        file2 = self._create_file("test2.txt", "World")
        hash1 = self.tracker.compute_hash(file1)
        hash2 = self.tracker.compute_hash(file2)
        self.assertNotEqual(hash1, hash2)

    # --- Tests detect_changes ---
    def test_detect_new_files(self):
        """Detection of new files."""
        self._create_file("new_file.txt")
        
        result = self.tracker.detect_changes()
        
        self.assertTrue(result.has_changes)
        self.assertEqual(len(result.new_files), 1)
        self.assertEqual(result.new_files[0].name, "new_file.txt")
        self.assertEqual(len(result.modified_files), 0)
        self.assertEqual(len(result.deleted_files), 0)

    def test_detect_modified_files(self):
        """Detection of modified files."""
        filepath = self._create_file("conv.txt", "original content")
        
        # Index the file
        self.tracker.update_file_state(filepath, ["chunk_1"])
        self.tracker.save_state()
        
        # Modify the file
        filepath.write_text("modified content", encoding='utf-8')
        
        # Reload and detect
        tracker2 = DeltaTracker(self.config)
        result = tracker2.detect_changes()
        
        self.assertTrue(result.has_changes)
        self.assertEqual(len(result.modified_files), 1)
        self.assertEqual(result.modified_files[0].name, "conv.txt")

    def test_detect_deleted_files(self):
        """Detection of deleted files."""
        filepath = self._create_file("to_delete.txt")
        
        # Index the file
        self.tracker.update_file_state(filepath, ["chunk_1"])
        self.tracker.save_state()
        
        # Delete the file
        filepath.unlink()
        
        # Reload and detect
        tracker2 = DeltaTracker(self.config)
        result = tracker2.detect_changes()
        
        self.assertTrue(result.has_changes)
        self.assertEqual(len(result.deleted_files), 1)
        self.assertIn("to_delete.txt", result.deleted_files[0])

    def test_detect_no_changes(self):
        """No changes if nothing moved."""
        filepath = self._create_file("stable.txt")
        
        # Index
        self.tracker.update_file_state(filepath, ["chunk_1"])
        self.tracker.save_state()
        
        # Reload and check
        tracker2 = DeltaTracker(self.config)
        result = tracker2.detect_changes()
        
        self.assertFalse(result.has_changes)

    # --- Tests update_file_state ---
    def test_update_file_state(self):
        """Update state after indexing."""
        filepath = self._create_file("indexed.txt")
        chunk_ids = ["chunk_1", "chunk_2"]
        
        self.tracker.update_file_state(filepath, chunk_ids)
        
        path_str = str(filepath)
        self.assertIn(path_str, self.tracker.file_states)
        state = self.tracker.file_states[path_str]
        self.assertEqual(state.chunk_ids, chunk_ids)
        self.assertIsNotNone(state.content_hash)
        self.assertIsNotNone(state.last_indexed)

    # --- Tests save/load state ---
    def test_save_load_state(self):
        """Save and reload state."""
        filepath = self._create_file("persistent.txt")
        self.tracker.update_file_state(filepath, ["chunk_1"])
        self.tracker.save_state()
        
        # Reload
        tracker2 = DeltaTracker(self.config)
        
        self.assertEqual(len(tracker2.file_states), 1)
        path_str = str(filepath)
        self.assertIn(path_str, tracker2.file_states)

    # --- Tests get_chunk_ids_for_file ---
    def test_get_chunk_ids_for_file(self):
        """Get chunk IDs for a file."""
        filepath = self._create_file("with_chunks.txt")
        expected_chunks = ["chunk_a", "chunk_b", "chunk_c"]
        self.tracker.update_file_state(filepath, expected_chunks)
        
        result = self.tracker.get_chunk_ids_for_file(str(filepath))
        self.assertEqual(result, expected_chunks)

    def test_get_chunk_ids_unknown_file(self):
        """Returns empty list for unknown file."""
        result = self.tracker.get_chunk_ids_for_file("/unknown/file.txt")
        self.assertEqual(result, [])

    # --- Tests get_stats ---
    def test_get_stats(self):
        """Tracking statistics."""
        self._create_file("file1.txt", "a" * 100)
        self._create_file("file2.txt", "b" * 200)
        
        for f in self.conv_dir.glob("*.txt"):
            self.tracker.update_file_state(f, [f"chunk_{f.name}"])
        
        stats = self.tracker.get_stats()
        
        self.assertEqual(stats['tracked_files'], 2)
        self.assertEqual(stats['total_chunks'], 2)
        self.assertGreater(stats['total_size_bytes'], 0)

    # --- Tests clear ---
    def test_clear(self):
        """Clear state."""
        filepath = self._create_file("to_clear.txt")
        self.tracker.update_file_state(filepath, ["chunk_1"])
        self.tracker.save_state()
        
        self.tracker.clear()
        
        self.assertEqual(len(self.tracker.file_states), 0)
        self.assertFalse(self.tracker.state_path.exists())


class TestDeltaResult(unittest.TestCase):
    
    def test_has_changes_new(self):
        """has_changes True if new files."""
        result = DeltaResult(
            new_files=[Path("new.txt")],
            modified_files=[],
            deleted_files=[]
        )
        self.assertTrue(result.has_changes)

    def test_has_changes_none(self):
        """has_changes False if no changes."""
        result = DeltaResult(
            new_files=[],
            modified_files=[],
            deleted_files=[]
        )
        self.assertFalse(result.has_changes)

    def test_summary(self):
        """summary returns a readable summary."""
        result = DeltaResult(
            new_files=[Path("a.txt"), Path("b.txt")],
            modified_files=[Path("c.txt")],
            deleted_files=["d.txt"]
        )
        summary = result.summary()
        self.assertIn("New: 2", summary)
        self.assertIn("Modified: 1", summary)
        self.assertIn("Deleted: 1", summary)


if __name__ == '__main__':
    unittest.main()