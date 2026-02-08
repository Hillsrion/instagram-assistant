"""
Tests for enrichment_chunking.py module.
Semantic enrichment and chunking.
"""
import unittest
from unittest.mock import MagicMock, patch
import os
import shutil
import tempfile
from pathlib import Path
import json
import datetime

# Import project modules
from rag_pipeline.core.config import Config
from rag_pipeline.indexing.chunker import ConversationChunker
from rag_pipeline.core.models import Chunk, Message
from rag_pipeline.enrichment.enricher import ChunkEnricher

class TestEnrichmentChunking(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.conversations_dir = Path(self.test_dir) / "conversations"
        self.conversations_dir.mkdir()
        self.rag_data_dir = Path(self.test_dir) / "rag_data"
        self.rag_data_dir.mkdir()

        # Config setup
        self.config = Config(
            base_dir=Path(self.test_dir),
            conversations_dir=self.conversations_dir,
            index_dir=self.rag_data_dir,
            chunk_max_messages=10, # Low number to force splitting easily
            chunk_time_gap=1.0 # 1 hour gap
        )

        # Helper to create dummy conversation files
        self.create_dummy_conversation("conv1.txt", 5)
        self.create_dummy_conversation("conv2.txt", 5)
        self.create_dummy_conversation("conv3.txt", 5)
        self.create_dummy_conversation("conv4.txt", 5) # For limit testing

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def create_dummy_conversation(self, filename, num_messages, start_time=None):
        if start_time is None:
            start_time = datetime.datetime.now()
        
        filepath = self.conversations_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# Conversation Instagram avec TestUser\n")
            f.write(f"ID: {filename.split('.')[0]}\n")
            f.write("Participants: Moi, TestUser\n")
            f.write("="*10 + "\n")
            
            for i in range(num_messages):
                msg_time = start_time + datetime.timedelta(minutes=i*5)
                f.write(f"[{msg_time.strftime('%Y-%m-%d %H:%M:%S')}] TestUser:\n")
                f.write(f"Message {i}\n")
                f.write("\n")

    def test_enrich_text_valid(self):
        """Test unit: enrich_text with valid data (Mocked LLM)"""
        enricher = ChunkEnricher(self.config)
        chunk = Chunk(
            chunk_id="test_chunk",
            conversation_id="test_conv",
            participants=["A", "B"],
            date_start="2023-01-01",
            date_end="2023-01-01",
            message_count=5,
            content="Some content",
            file_source="test.txt"
        )

        mock_response = {
            "narrative_summary": "Narrative summary",
            "questions": ["Q1", "Q2", "Q3"],
            "speaker_intents": {"A": "Intent A"},
            "temporal_context": "Summer",
            "entities": {"locations": ["Paris"]},
            "emotions": {"dominant": "Joy"},
            "interaction_pattern": "Debate",
            "initiative": "A",
            "emotional_shift": "Stable",
            "open_loops": []
        }

        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"message": {"content": json.dumps(mock_response)}}

            # Act
            result = enricher.enrich_chunk(chunk)
            
            # Assert
            self.assertEqual(result[0], "Narrative summary")
            self.assertEqual(result[1], ["Q1", "Q2", "Q3"])
            self.assertEqual(result[4]["locations"], ["Paris"])
            self.assertEqual(result[6], "Debate")  # interaction_pattern

    @patch('builtins.print')
    def test_enrich_text_invalid(self, mock_print):
        """Test unit: enrich_text with invalid data (API failure)"""
        enricher = ChunkEnricher(self.config)
        chunk = Chunk(
            chunk_id="test_chunk",
            conversation_id="test_conv",
            participants=["A", "B"],
            date_start="2023-01-01",
            date_end="2023-01-01",
            message_count=5,
            content="Some content",
            file_source="test.txt"
        )

        with patch('requests.post') as mock_post:
            mock_post.side_effect = Exception("API Error")

            # Act
            result = enricher.enrich_chunk(chunk)

            # Assert - should return empty fallbacks
            self.assertEqual(result[0], "")
            self.assertEqual(result[1], [])
            self.assertEqual(result[2], {})
            self.assertIsNone(result[6])

    def test_chunk_text_long(self):
        """Test unit: chunk_text with long text (should split)"""
        # Create a conversation with 25 messages (limit is 10)
        self.create_dummy_conversation("long_conv.txt", 25)
        
        chunker = ConversationChunker(self.config)
        chunks = chunker.chunk_conversation(self.conversations_dir / "long_conv.txt")
        
        # Expecting at least 3 chunks (10 per chunk approx)
        self.assertTrue(len(chunks) >= 3)
        self.assertEqual(chunks[0].conversation_id, "long_conv")

    def test_chunk_text_short(self):
        """Test unit: chunk_text with short text (no split)"""
        # Create a conversation with 5 messages (limit is 10)
        self.create_dummy_conversation("short_conv.txt", 5)
        
        chunker = ConversationChunker(self.config)
        chunks = chunker.chunk_conversation(self.conversations_dir / "short_conv.txt")
        
        self.assertEqual(len(chunks), 1)

    def test_process_conversation_chunking_only(self):
        """Test integration: process conversation (chunking only)"""
        chunker = ConversationChunker(self.config)
        # Using one of the setup files
        chunks = chunker.chunk_conversation(self.conversations_dir / "conv1.txt")
        self.assertTrue(len(chunks) > 0)
        self.assertIsNotNone(chunks[0].content)

    def test_process_conversation_enrichment_only(self):
        """Test integration: process conversation (enrichment only logic)"""
        # Manually create a chunk and enrich it
        chunk = Chunk(
            chunk_id="integration_test",
            conversation_id="conv1",
            participants=["Moi", "User"],
            date_start="2023-01-01",
            date_end="2023-01-01",
            message_count=5,
            content="Hello world",
            file_source="conv1.txt"
        )
        
        enricher = ChunkEnricher(self.config)
        
        mock_response = {
            "narrative_summary": "Integration Test Summary",
            "questions": ["Q1"], 
            "speaker_intents": {},
            "temporal_context": "",
            "entities": {},
            "emotions": {}
        }
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"message": {"content": json.dumps(mock_response)}}
            
            summary, questions, _, _, _, _, _, _, _, _ = enricher.enrich_chunk(chunk)
            chunk.narrative_summary = summary
            chunk.hypothetical_questions = questions
            
            self.assertEqual(chunk.narrative_summary, "Integration Test Summary")

    def test_process_conversation_combined(self):
        """Test integration: process conversation (chunking + enrichment)"""
        # 1. Chunk
        chunker = ConversationChunker(self.config)
        chunks = chunker.chunk_conversation(self.conversations_dir / "conv1.txt")
        self.assertTrue(len(chunks) > 0)
        
        # 2. Enrich
        enricher = ChunkEnricher(self.config)
        mock_response = {
            "narrative_summary": "Combined Test Summary",
            "questions": ["Why?"],
            "speaker_intents": {},
            "temporal_context": "",
            "entities": {},
            "emotions": {}
        }
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"message": {"content": json.dumps(mock_response)}}
            
            enriched_chunks = enricher.enrich_batch(chunks)
            
            self.assertEqual(enriched_chunks[0].narrative_summary, "Combined Test Summary")

    def test_limit_conversations(self):
        """Test limits: verify max 3 conversations processed"""
        chunker = ConversationChunker(self.config)
        
        chunks = chunker.chunk_all_conversations(limit=3)
        
        # Extract unique source files from chunks
        source_files = set(c.file_source for c in chunks)
        
        self.assertEqual(len(source_files), 3)

if __name__ == '__main__':
    unittest.main()