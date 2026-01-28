"""
Tests pour le module analytics.py
Analytics et statistiques sur les conversations.
"""
import unittest
import tempfile
import shutil
import sqlite3
from pathlib import Path

from rag_pipeline.config import Config
from rag_pipeline.analytics import ConversationAnalytics
from rag_pipeline.metadata_store import MetadataStore
from rag_pipeline.chunker import Chunk


class TestConversationAnalytics(unittest.TestCase):

    def setUp(self):
        """Setup avec répertoire temporaire et base SQLite"""
        self.test_dir = tempfile.mkdtemp()
        self.config = Config(
            base_dir=Path(self.test_dir),
            index_dir=Path(self.test_dir) / "rag_data"
        )
        
        # Créer d'abord le MetadataStore pour peupler la base
        self.metadata_store = MetadataStore(self.config)
        
        # Créer et indexer des chunks de test
        self.chunks = self._create_sample_chunks()
        self.metadata_store.build_index(self.chunks)
        self.metadata_store.close()
        
        # Maintenant créer l'analytics
        self.analytics = ConversationAnalytics(self.config)

    def tearDown(self):
        """Nettoyage"""
        self.analytics.close()
        shutil.rmtree(self.test_dir)

    def _create_chunk(
        self, 
        chunk_id: str, 
        participants: list,
        date_start: str,
        date_end: str,
        conversation_id: str,
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
        return [
            self._create_chunk("c1", ["Alice", "Bob"], "2024-01-15", "2024-01-20", "conv_1", 50),
            self._create_chunk("c2", ["Alice", "Charlie"], "2024-02-01", "2024-02-10", "conv_2", 30),
            self._create_chunk("c3", ["Bob", "David"], "2024-03-01", "2024-03-15", "conv_3", 40),
            self._create_chunk("c4", ["Alice", "Bob"], "2024-01-25", "2024-01-31", "conv_1", 25),
            self._create_chunk("c5", ["Charlie", "Eve"], "2023-06-01", "2023-06-30", "conv_4", 60),
        ]

    # --- Tests count_messages ---
    def test_count_messages_total(self):
        """Comptage total des messages"""
        count = self.analytics.count_messages()
        
        # 50 + 30 + 40 + 25 + 60 = 205
        self.assertEqual(count, 205)

    def test_count_messages_by_participant(self):
        """Comptage des messages par participant"""
        count = self.analytics.count_messages(participant="Alice")
        
        # Alice: c1 (50) + c2 (30) + c4 (25) = 105
        self.assertEqual(count, 105)

    def test_count_messages_by_date_range(self):
        """Comptage des messages par période"""
        count = self.analytics.count_messages(
            date_start="2024-01-01",
            date_end="2024-01-31"
        )
        
        # c1 (50) + c4 (25) = 75
        self.assertEqual(count, 75)

    def test_count_messages_by_conversation(self):
        """Comptage des messages par conversation"""
        count = self.analytics.count_messages(conversation_id="conv_1")
        
        # conv_1: c1 (50) + c4 (25) = 75
        self.assertEqual(count, 75)

    def test_count_messages_combined_filters(self):
        """Comptage avec filtres combinés"""
        count = self.analytics.count_messages(
            participant="Bob",
            date_start="2024-01-01",
            date_end="2024-01-31"
        )
        
        # Bob en janvier 2024: c1 (50) + c4 (25) = 75
        self.assertEqual(count, 75)

    # --- Tests get_participant_stats ---
    def test_get_participant_stats(self):
        """Statistiques par participant"""
        stats = self.analytics.get_participant_stats()
        
        # Les noms sont stockés en lowercase
        self.assertIn("alice", stats)
        self.assertIn("bob", stats)
        
        # Vérifier la structure
        alice_stats = stats["alice"]
        self.assertIn("message_count", alice_stats)
        self.assertIn("conversations", alice_stats)
        self.assertIn("chunks", alice_stats)

    def test_get_participant_stats_counts(self):
        """Vérification des comptages par participant"""
        stats = self.analytics.get_participant_stats()
        
        # alice: 3 chunks (c1, c2, c4), 105 messages (lowercase key)
        self.assertEqual(stats["alice"]["message_count"], 105)
        self.assertEqual(stats["alice"]["chunks"], 3)

    # --- Tests get_date_range ---
    def test_get_date_range(self):
        """Récupération de la plage de dates globale"""
        start, end = self.analytics.get_date_range()
        
        self.assertEqual(start, "2023-06-01")  # c5
        self.assertEqual(end, "2024-03-15")    # c3

    # --- Tests get_conversation_stats ---
    def test_get_conversation_stats(self):
        """Statistiques globales des conversations"""
        stats = self.analytics.get_conversation_stats()
        
        self.assertEqual(stats["total_messages"], 205)
        self.assertEqual(stats["total_chunks"], 5)
        self.assertIn("total_conversations", stats)
        self.assertIn("total_participants", stats)
        self.assertIn("date_start", stats)
        self.assertIn("date_end", stats)

    def test_get_conversation_stats_participants_count(self):
        """Comptage des participants uniques"""
        stats = self.analytics.get_conversation_stats()
        
        # Alice, Bob, Charlie, David, Eve = 5
        self.assertEqual(stats["total_participants"], 5)

    # --- Tests get_conversation_timeline ---
    def test_get_conversation_timeline(self):
        """Timeline des conversations avec un participant"""
        timeline = self.analytics.get_conversation_timeline("Alice")
        
        # Alice est dans conv_1 et conv_2
        self.assertGreater(len(timeline), 0)
        
        # Vérifier la structure
        for record in timeline:
            self.assertIn("conversation_id", record)
            self.assertIn("date_start", record)
            self.assertIn("date_end", record)

    # --- Tests get_message_count_by_month ---
    def test_get_message_count_by_month(self):
        """Messages par mois"""
        monthly = self.analytics.get_message_count_by_month()
        
        self.assertGreater(len(monthly), 0)
        
        # Vérifier la structure
        for record in monthly:
            self.assertIn("year", record)
            self.assertIn("month", record)
            self.assertIn("message_count", record)

    def test_get_message_count_by_month_filtered(self):
        """Messages par mois filtrés par participant"""
        monthly = self.analytics.get_message_count_by_month(participant="Alice")
        
        # Vérifier que seuls les messages d'Alice sont comptés
        total = sum(m["message_count"] for m in monthly)
        self.assertEqual(total, 105)  # Total d'Alice


if __name__ == '__main__':
    unittest.main()
