"""
Tests pour le module delta_tracker.py
Suivi des modifications de fichiers pour l'indexation incrémentale.
"""
import unittest
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime

from rag_pipeline.config import Config
from rag_pipeline.delta_tracker import DeltaTracker, FileState, DeltaResult


class TestDeltaTracker(unittest.TestCase):

    def setUp(self):
        """Création d'un répertoire temporaire"""
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
        """Nettoyage du répertoire temporaire"""
        shutil.rmtree(self.test_dir)

    def _create_file(self, filename: str, content: str = "test content") -> Path:
        """Helper pour créer un fichier"""
        filepath = self.conv_dir / filename
        filepath.write_text(content, encoding='utf-8')
        return filepath

    # --- Tests compute_hash ---
    def test_compute_hash_consistent(self):
        """Le hash est consistent pour le même contenu"""
        file1 = self._create_file("test1.txt", "Hello World")
        hash1 = self.tracker.compute_hash(file1)
        hash2 = self.tracker.compute_hash(file1)
        self.assertEqual(hash1, hash2)

    def test_compute_hash_different_content(self):
        """Le hash change avec le contenu"""
        file1 = self._create_file("test1.txt", "Hello")
        file2 = self._create_file("test2.txt", "World")
        hash1 = self.tracker.compute_hash(file1)
        hash2 = self.tracker.compute_hash(file2)
        self.assertNotEqual(hash1, hash2)

    # --- Tests detect_changes ---
    def test_detect_new_files(self):
        """Détection des nouveaux fichiers"""
        self._create_file("new_file.txt")
        
        result = self.tracker.detect_changes()
        
        self.assertTrue(result.has_changes)
        self.assertEqual(len(result.new_files), 1)
        self.assertEqual(result.new_files[0].name, "new_file.txt")
        self.assertEqual(len(result.modified_files), 0)
        self.assertEqual(len(result.deleted_files), 0)

    def test_detect_modified_files(self):
        """Détection des fichiers modifiés"""
        filepath = self._create_file("conv.txt", "original content")
        
        # Indexer le fichier
        self.tracker.update_file_state(filepath, ["chunk_1"])
        self.tracker.save_state()
        
        # Modifier le fichier
        filepath.write_text("modified content", encoding='utf-8')
        
        # Recharger et détecter
        tracker2 = DeltaTracker(self.config)
        result = tracker2.detect_changes()
        
        self.assertTrue(result.has_changes)
        self.assertEqual(len(result.modified_files), 1)
        self.assertEqual(result.modified_files[0].name, "conv.txt")

    def test_detect_deleted_files(self):
        """Détection des fichiers supprimés"""
        filepath = self._create_file("to_delete.txt")
        
        # Indexer le fichier
        self.tracker.update_file_state(filepath, ["chunk_1"])
        self.tracker.save_state()
        
        # Supprimer le fichier
        filepath.unlink()
        
        # Recharger et détecter
        tracker2 = DeltaTracker(self.config)
        result = tracker2.detect_changes()
        
        self.assertTrue(result.has_changes)
        self.assertEqual(len(result.deleted_files), 1)
        self.assertIn("to_delete.txt", result.deleted_files[0])

    def test_detect_no_changes(self):
        """Pas de changements si rien n'a bougé"""
        filepath = self._create_file("stable.txt")
        
        # Indexer
        self.tracker.update_file_state(filepath, ["chunk_1"])
        self.tracker.save_state()
        
        # Recharger et vérifier
        tracker2 = DeltaTracker(self.config)
        result = tracker2.detect_changes()
        
        self.assertFalse(result.has_changes)

    # --- Tests update_file_state ---
    def test_update_file_state(self):
        """Mise à jour de l'état après indexation"""
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
        """Sauvegarde et rechargement de l'état"""
        filepath = self._create_file("persistent.txt")
        self.tracker.update_file_state(filepath, ["chunk_1"])
        self.tracker.save_state()
        
        # Recharger
        tracker2 = DeltaTracker(self.config)
        
        self.assertEqual(len(tracker2.file_states), 1)
        path_str = str(filepath)
        self.assertIn(path_str, tracker2.file_states)

    # --- Tests get_chunk_ids_for_file ---
    def test_get_chunk_ids_for_file(self):
        """Récupération des chunk IDs pour un fichier"""
        filepath = self._create_file("with_chunks.txt")
        expected_chunks = ["chunk_a", "chunk_b", "chunk_c"]
        self.tracker.update_file_state(filepath, expected_chunks)
        
        result = self.tracker.get_chunk_ids_for_file(str(filepath))
        self.assertEqual(result, expected_chunks)

    def test_get_chunk_ids_unknown_file(self):
        """Retourne liste vide pour fichier inconnu"""
        result = self.tracker.get_chunk_ids_for_file("/unknown/file.txt")
        self.assertEqual(result, [])

    # --- Tests get_stats ---
    def test_get_stats(self):
        """Statistiques de suivi"""
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
        """Effacement de l'état"""
        filepath = self._create_file("to_clear.txt")
        self.tracker.update_file_state(filepath, ["chunk_1"])
        self.tracker.save_state()
        
        self.tracker.clear()
        
        self.assertEqual(len(self.tracker.file_states), 0)
        self.assertFalse(self.tracker.state_path.exists())


class TestDeltaResult(unittest.TestCase):
    
    def test_has_changes_new(self):
        """has_changes True si nouveaux fichiers"""
        result = DeltaResult(
            new_files=[Path("new.txt")],
            modified_files=[],
            deleted_files=[]
        )
        self.assertTrue(result.has_changes)

    def test_has_changes_none(self):
        """has_changes False si aucun changement"""
        result = DeltaResult(
            new_files=[],
            modified_files=[],
            deleted_files=[]
        )
        self.assertFalse(result.has_changes)

    def test_summary(self):
        """summary retourne un résumé lisible"""
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
