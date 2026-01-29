"""
Tests for JSON storage functions.
"""
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from api import storage


class TestStorage(unittest.TestCase):
    """Tests for storage module."""

    def setUp(self):
        """Creates a temporary file for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = Path(self.temp_dir) / "test_conversations.json"

    def tearDown(self):
        """Cleans up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch.object(storage, 'CONVERSATIONS_FILE')
    def test_load_conversations_empty(self, mock_file):
        """load_conversations returns empty dict if file doesn't exist."""
        mock_file.__class__ = Path
        mock_file.exists.return_value = False
        
        # Patch the Path object properly
        with patch.object(storage, 'CONVERSATIONS_FILE', self.temp_file):
            result = storage.load_conversations()
            self.assertEqual(result, {})

    @patch.object(storage, 'CONVERSATIONS_FILE')
    def test_save_and_load_conversations(self, mock_file):
        """Saving and loading conversations."""
        with patch.object(storage, 'CONVERSATIONS_FILE', self.temp_file):
            # Save
            conversations = {
                "abc123": {
                    "id": "abc123",
                    "title": "Test",
                    "created_at": "2024-01-01T12:00:00",
                    "updated_at": "2024-01-01T12:00:00",
                    "messages": []
                }
            }
            storage.save_conversations(conversations)
            
            # Verify file exists
            self.assertTrue(self.temp_file.exists())
            
            # Load
            loaded = storage.load_conversations()
            self.assertEqual(loaded, conversations)

    @patch.object(storage, 'CONVERSATIONS_FILE')
    def test_get_conversation(self, mock_file):
        """get_conversation returns the conversation or None."""
        with patch.object(storage, 'CONVERSATIONS_FILE', self.temp_file):
            # Create data
            conversations = {
                "abc123": {"id": "abc123", "title": "Test"}
            }
            storage.save_conversations(conversations)
            
            # Test existing
            conv = storage.get_conversation("abc123")
            self.assertIsNotNone(conv)
            self.assertEqual(conv["title"], "Test")
            
            # Test non-existing
            conv = storage.get_conversation("nonexistent")
            self.assertIsNone(conv)

    @patch.object(storage, 'CONVERSATIONS_FILE')
    def test_save_conversation(self, mock_file):
        """save_conversation adds/updates a conversation."""
        with patch.object(storage, 'CONVERSATIONS_FILE', self.temp_file):
            # Save first conversation
            conv1 = {"id": "abc123", "title": "First"}
            storage.save_conversation(conv1)
            
            # Verify
            loaded = storage.load_conversations()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded["abc123"]["title"], "First")
            
            # Update
            conv1_updated = {"id": "abc123", "title": "Updated"}
            storage.save_conversation(conv1_updated)
            
            loaded = storage.load_conversations()
            self.assertEqual(loaded["abc123"]["title"], "Updated")

    @patch.object(storage, 'CONVERSATIONS_FILE')
    def test_delete_conversation(self, mock_file):
        """delete_conversation removes a conversation."""
        with patch.object(storage, 'CONVERSATIONS_FILE', self.temp_file):
            # Create data
            conversations = {
                "abc123": {"id": "abc123", "title": "Test"},
                "def456": {"id": "def456", "title": "Other"}
            }
            storage.save_conversations(conversations)
            
            # Delete
            result = storage.delete_conversation("abc123")
            self.assertTrue(result)
            
            # Verify
            loaded = storage.load_conversations()
            self.assertEqual(len(loaded), 1)
            self.assertNotIn("abc123", loaded)
            
            # Delete non-existing
            result = storage.delete_conversation("nonexistent")
            self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()