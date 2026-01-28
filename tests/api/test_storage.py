"""
Tests pour les fonctions de stockage JSON des conversations.
"""
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from api import storage


class TestStorage(unittest.TestCase):
    """Tests pour le module storage."""

    def setUp(self):
        """Crée un fichier temporaire pour les tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = Path(self.temp_dir) / "test_conversations.json"

    def tearDown(self):
        """Nettoie les fichiers temporaires."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch.object(storage, 'CONVERSATIONS_FILE')
    def test_load_conversations_empty(self, mock_file):
        """load_conversations retourne dict vide si fichier n'existe pas."""
        mock_file.__class__ = Path
        mock_file.exists.return_value = False
        
        # Patch the Path object properly
        with patch.object(storage, 'CONVERSATIONS_FILE', self.temp_file):
            result = storage.load_conversations()
            self.assertEqual(result, {})

    @patch.object(storage, 'CONVERSATIONS_FILE')
    def test_save_and_load_conversations(self, mock_file):
        """Sauvegarde et rechargement de conversations."""
        with patch.object(storage, 'CONVERSATIONS_FILE', self.temp_file):
            # Sauvegarder
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
            
            # Vérifier que le fichier existe
            self.assertTrue(self.temp_file.exists())
            
            # Recharger
            loaded = storage.load_conversations()
            self.assertEqual(loaded, conversations)

    @patch.object(storage, 'CONVERSATIONS_FILE')
    def test_get_conversation(self, mock_file):
        """get_conversation retourne la conversation ou None."""
        with patch.object(storage, 'CONVERSATIONS_FILE', self.temp_file):
            # Créer des données
            conversations = {
                "abc123": {"id": "abc123", "title": "Test"}
            }
            storage.save_conversations(conversations)
            
            # Test existant
            conv = storage.get_conversation("abc123")
            self.assertIsNotNone(conv)
            self.assertEqual(conv["title"], "Test")
            
            # Test non existant
            conv = storage.get_conversation("nonexistent")
            self.assertIsNone(conv)

    @patch.object(storage, 'CONVERSATIONS_FILE')
    def test_save_conversation(self, mock_file):
        """save_conversation ajoute/met à jour une conversation."""
        with patch.object(storage, 'CONVERSATIONS_FILE', self.temp_file):
            # Sauvegarder première conversation
            conv1 = {"id": "abc123", "title": "First"}
            storage.save_conversation(conv1)
            
            # Vérifier
            loaded = storage.load_conversations()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded["abc123"]["title"], "First")
            
            # Mettre à jour
            conv1_updated = {"id": "abc123", "title": "Updated"}
            storage.save_conversation(conv1_updated)
            
            loaded = storage.load_conversations()
            self.assertEqual(loaded["abc123"]["title"], "Updated")

    @patch.object(storage, 'CONVERSATIONS_FILE')
    def test_delete_conversation(self, mock_file):
        """delete_conversation supprime une conversation."""
        with patch.object(storage, 'CONVERSATIONS_FILE', self.temp_file):
            # Créer des données
            conversations = {
                "abc123": {"id": "abc123", "title": "Test"},
                "def456": {"id": "def456", "title": "Other"}
            }
            storage.save_conversations(conversations)
            
            # Supprimer
            result = storage.delete_conversation("abc123")
            self.assertTrue(result)
            
            # Vérifier
            loaded = storage.load_conversations()
            self.assertEqual(len(loaded), 1)
            self.assertNotIn("abc123", loaded)
            
            # Supprimer non existant
            result = storage.delete_conversation("nonexistent")
            self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
