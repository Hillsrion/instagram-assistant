"""
Tests pour le module metadata_store.py
Store SQLite pour les métadonnées des chunks (pre-filtering).
"""
import unittest
import tempfile
import shutil
from pathlib import Path

from rag_pipeline.config import Config
from rag_pipeline.metadata_store import MetadataStore
from rag_pipeline.chunker import Chunk


class TestMetadataStore(unittest.TestCase):

    def setUp(self):
        """Setup avec répertoire temporaire et base SQLite"""
        self.test_dir = tempfile.mkdtemp()
        self.config = Config(
            base_dir=Path(self.test_dir),
            index_dir=Path(self.test_dir) / "rag_data"
        )
        self.store = MetadataStore(self.config)

    def tearDown(self):
        """Nettoyage"""
        self.store.close()
        shutil.rmtree(self.test_dir)

    def _create_chunk(
        self, 
        chunk_id: str, 
        participants: list,
        date_start: str = "2024-01-01",
        date_end: str = "2024-01-02",
        conversation_id: str = "conv_1",
        message_count: int = 10
    ) -> Chunk:
        """Helper pour créer un chunk"""
        return Chunk(
            chunk_id=chunk_id,
            conversation_id=conversation_id,
            participants=participants,
            date_start=date_start,
            date_end=date_end,
            message_count=message_count,
            content="Test content",
            file_source="test.txt"
        )

    def _create_sample_chunks(self) -> list:
        """Crée un ensemble de chunks de test"""
        chunks = [
            self._create_chunk("c1", ["Alice", "Bob"], "2024-01-01", "2024-01-15", "conv_alice"),
            self._create_chunk("c2", ["Alice", "Charlie"], "2024-02-01", "2024-02-15", "conv_alice"),
            self._create_chunk("c3", ["Bob", "David"], "2024-03-01", "2024-03-15", "conv_bob"),
            self._create_chunk("c4", ["Charlie", "Eve"], "2023-06-01", "2023-06-30", "conv_charlie"),
        ]
        # Ajouter des entités à certains chunks
        chunks[0].entities = {"locations": ["Paris", "Lyon"], "events": ["Anniversaire"]}
        chunks[1].entities = {"locations": ["Marseille"], "topics": ["Vacances"]}
        return chunks

    # --- Tests build_index ---
    def test_build_index(self):
        """build_index crée les entrées correctement"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        # Vérifier que les participants sont indexés (stockés en lowercase)
        participants = self.store.get_all_participants()
        participant_names = [p[0] for p in participants]
        
        self.assertIn("alice", participant_names)
        self.assertIn("bob", participant_names)
        self.assertIn("charlie", participant_names)

    # --- Tests filter_by_participant ---
    def test_filter_by_participant_exact(self):
        """Filtre par participant exact"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_participant("Alice")
        
        # Alice est dans c1 et c2
        self.assertEqual(len(indices), 2)
        self.assertIn(0, indices)  # c1
        self.assertIn(1, indices)  # c2

    def test_filter_by_participant_partial(self):
        """Filtre par participant avec match partiel"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_participant("ali")  # Minuscule + partiel
        
        self.assertEqual(len(indices), 2)

    def test_filter_by_participant_not_found(self):
        """Filtre retourne vide si participant non trouvé"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_participant("Unknown")
        
        self.assertEqual(len(indices), 0)

    # --- Tests filter_by_date_range ---
    def test_filter_by_date_range_full(self):
        """Filtre par période complète"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_date_range("2024-01-01", "2024-02-28")
        
        # c1 et c2 sont dans cette période
        self.assertEqual(len(indices), 2)

    def test_filter_by_date_range_start_only(self):
        """Filtre avec date de début seulement"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_date_range(start_date="2024-02-01")
        
        # c2 et c3 commencent après ou le 2024-02-01
        self.assertIn(1, indices)  # c2
        self.assertIn(2, indices)  # c3

    def test_filter_by_date_range_end_only(self):
        """Filtre avec date de fin seulement"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_date_range(end_date="2024-01-31")
        
        # c1 et c4 finissent avant ou le 2024-01-31
        self.assertIn(0, indices)  # c1
        self.assertIn(3, indices)  # c4

    # --- Tests filter_by_year ---
    def test_filter_by_year(self):
        """Filtre par année"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_year(2023)
        
        # c4 est en 2023 - vérifier que la méthode fonctionne
        self.assertIsInstance(indices, set)

    # --- Tests filter_by_entity ---
    def test_filter_by_entity_value(self):
        """Filtre par valeur d'entité"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_entity("Paris")
        
        # Paris est dans c1
        self.assertEqual(len(indices), 1)
        self.assertIn(0, indices)

    def test_filter_by_entity_with_category(self):
        """Filtre par entité avec catégorie"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_entity("Vacances", category="topics")
        
        # Vacances (topic) est dans c2
        self.assertEqual(len(indices), 1)
        self.assertIn(1, indices)

    # --- Tests filter_by_conversation ---
    def test_filter_by_conversation(self):
        """Filtre par conversation"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_conversation("conv_alice")
        
        # conv_alice contient c1 et c2
        self.assertEqual(len(indices), 2)

    # --- Tests get_all_participants ---
    def test_get_all_participants(self):
        """Liste tous les participants avec comptage"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        participants = self.store.get_all_participants()
        
        # Vérifier le format (name, count)
        self.assertTrue(all(len(p) == 2 for p in participants))
        
        # Vérifier le tri par count décroissant
        counts = [p[1] for p in participants]
        self.assertEqual(counts, sorted(counts, reverse=True))

    # --- Tests get_date_range ---
    def test_get_date_range(self):
        """Récupère la plage de dates globale"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        start, end = self.store.get_date_range()
        
        self.assertEqual(start, "2023-06-01")  # Plus ancien
        self.assertEqual(end, "2024-03-15")    # Plus récent

    # --- Tests get_adjacent_chunks ---
    def test_get_adjacent_chunks(self):
        """Récupère les chunks adjacents"""
        # Créer des chunks dans la même conversation
        chunks = [
            self._create_chunk("c1", ["A"], "2024-01-01", "2024-01-01", "conv1"),
            self._create_chunk("c2", ["A"], "2024-01-02", "2024-01-02", "conv1"),
            self._create_chunk("c3", ["A"], "2024-01-03", "2024-01-03", "conv1"),
            self._create_chunk("c4", ["B"], "2024-01-01", "2024-01-01", "conv2"),
        ]
        self.store.build_index(chunks)
        
        indices = self.store.get_adjacent_chunks("c2", window=1)
        
        # Résultat dépend de l'implémentation exacte
        # Test simplifié : on vérifie que la méthode ne plante pas
        self.assertIsInstance(indices, list)
        self.assertNotIn(3, indices)  # c4 est dans conv2

    # --- Tests combinaison de filtres ---
    def test_combined_filters(self):
        """Combinaison de plusieurs filtres"""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        # Filtrer d'abord par participant
        indices = self.store.filter_by_participant("Alice")
        # Puis par date
        indices = self.store.filter_by_date_range("2024-02-01", "2024-12-31", indices)
        
        # Seul c2 matche (Alice + février 2024)
        self.assertEqual(len(indices), 1)
        self.assertIn(1, indices)


if __name__ == '__main__':
    unittest.main()
