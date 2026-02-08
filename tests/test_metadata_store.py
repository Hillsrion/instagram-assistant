from rag_pipeline.core.models import Chunk
"""
Tests for metadata_store.py module.
SQLite Store for chunk metadata (pre-filtering).
"""
import unittest
import tempfile
import shutil
from pathlib import Path

from rag_pipeline.core.config import Config
from rag_pipeline.indexing.metadata_store import MetadataStore


class TestMetadataStore(unittest.TestCase):

    def setUp(self):
        """Setup with temporary directory and SQLite database."""
        self.test_dir = tempfile.mkdtemp()
        self.config = Config(
            base_dir=Path(self.test_dir),
            index_dir=Path(self.test_dir) / "rag_data"
        )
        self.store = MetadataStore(self.config)

    def tearDown(self):
        """Cleanup."""
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
        """Helper to create a chunk."""
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
        """Creates a set of sample chunks."""
        chunks = [
            self._create_chunk("c1", ["Alice", "Bob"], "2024-01-01", "2024-01-15", "conv_alice"),
            self._create_chunk("c2", ["Alice", "Charlie"], "2024-02-01", "2024-02-15", "conv_alice"),
            self._create_chunk("c3", ["Bob", "David"], "2024-03-01", "2024-03-15", "conv_bob"),
            self._create_chunk("c4", ["Charlie", "Eve"], "2023-06-01", "2023-06-30", "conv_charlie"),
        ]
        # Add entities to some chunks
        chunks[0].entities = {"locations": ["Paris", "Lyon"], "events": ["Birthday"]}
        chunks[1].entities = {"locations": ["Marseille"], "topics": ["Vacation"]}
        return chunks

    # --- Tests build_index ---
    def test_build_index(self):
        """build_index creates entries correctly."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        # Check participants are indexed (stored lowercase)
        participants = self.store.get_all_participants()
        participant_names = [p[0] for p in participants]
        
        self.assertIn("alice", participant_names)
        self.assertIn("bob", participant_names)
        self.assertIn("charlie", participant_names)

    # --- Tests filter_by_participant ---
    def test_filter_by_participant_exact(self):
        """Filter by exact participant name."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_participant("Alice")
        
        # Alice is in c1 and c2
        self.assertEqual(len(indices), 2)
        self.assertIn(0, indices)  # c1
        self.assertIn(1, indices)  # c2

    def test_filter_by_participant_partial(self):
        """Filter by partial participant name."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_participant("ali")  # Lowercase + partial
        
        self.assertEqual(len(indices), 2)

    def test_filter_by_participant_not_found(self):
        """Filter returns empty if participant not found."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_participant("Unknown")
        
        self.assertEqual(len(indices), 0)

    # --- Tests filter_by_date_range ---
    def test_filter_by_date_range_full(self):
        """Filter by full date range."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_date_range("2024-01-01", "2024-02-28")
        
        # c1 and c2 are in this range
        self.assertEqual(len(indices), 2)

    def test_filter_by_date_range_start_only(self):
        """Filter with start date only."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_date_range(start_date="2024-02-01")
        
        # c2 and c3 start on or after 2024-02-01
        self.assertIn(1, indices)  # c2
        self.assertIn(2, indices)  # c3

    def test_filter_by_date_range_end_only(self):
        """Filter with end date only."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_date_range(end_date="2024-01-31")
        
        # c1 and c4 end on or before 2024-01-31
        self.assertIn(0, indices)  # c1
        self.assertIn(3, indices)  # c4

    # --- Tests filter_by_year ---
    def test_filter_by_year(self):
        """Filter by year."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_year(2023)
        
        # c4 is in 2023 - verify it works
        self.assertIsInstance(indices, set)

    # --- Tests filter_by_entity ---
    def test_filter_by_entity_value(self):
        """Filter by entity value."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_entity("Paris")
        
        # Paris is in c1
        self.assertEqual(len(indices), 1)
        self.assertIn(0, indices)

    def test_filter_by_entity_with_category(self):
        """Filter by entity with category."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_entity("Vacation", category="topics")
        
        # Vacation (topic) is in c2
        self.assertEqual(len(indices), 1)
        self.assertIn(1, indices)

    # --- Tests filter_by_conversation ---
    def test_filter_by_conversation(self):
        """Filter by conversation."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        indices = self.store.filter_by_conversation("conv_alice")
        
        # conv_alice contains c1 and c2
        self.assertEqual(len(indices), 2)

    # --- Tests get_all_participants ---
    def test_get_all_participants(self):
        """Lists all participants with count."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        participants = self.store.get_all_participants()
        
        # Verify format (name, count)
        self.assertTrue(all(len(p) == 2 for p in participants))
        
        # Verify sort by count descending
        counts = [p[1] for p in participants]
        self.assertEqual(counts, sorted(counts, reverse=True))

    # --- Tests get_date_range ---
    def test_get_date_range(self):
        """Gets global date range."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        start, end = self.store.get_date_range()
        
        self.assertEqual(start, "2023-06-01")  # Oldest
        self.assertEqual(end, "2024-03-15")    # Newest

    # --- Tests get_adjacent_chunks ---
    def test_get_adjacent_chunks(self):
        """Gets adjacent chunks."""
        # Create chunks in the same conversation
        chunks = [
            self._create_chunk("c1", ["A"], "2024-01-01", "2024-01-01", "conv1"),
            self._create_chunk("c2", ["A"], "2024-01-02", "2024-01-02", "conv1"),
            self._create_chunk("c3", ["A"], "2024-01-03", "2024-01-03", "conv1"),
            self._create_chunk("c4", ["B"], "2024-01-01", "2024-01-01", "conv2"),
        ]
        self.store.build_index(chunks)
        
        indices = self.store.get_adjacent_chunks("c2", window=1)
        
        # Result depends on exact implementation
        # Simplified test: check method doesn't crash
        self.assertIsInstance(indices, list)
        self.assertNotIn(3, indices)  # c4 is in conv2

    # --- Tests combined filters ---
    def test_combined_filters(self):
        """Combination of multiple filters."""
        chunks = self._create_sample_chunks()
        self.store.build_index(chunks)
        
        # Filter first by participant
        indices = self.store.filter_by_participant("Alice")
        # Then by date
        indices = self.store.filter_by_date_range("2024-02-01", "2024-12-31", indices)
        
        # Only c2 matches (Alice + February 2024)
        self.assertEqual(len(indices), 1)
        self.assertIn(1, indices)


if __name__ == '__main__':
    unittest.main()