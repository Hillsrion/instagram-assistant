"""
Tests for Pydantic API models.
"""
import unittest
from pydantic import ValidationError

from api.models import Message, Conversation, ChatRequest, ConversationCreate, TitleEvaluationRequest


class TestMessage(unittest.TestCase):
    """Tests for Message model."""

    def test_valid_message(self):
        """Valid message with all required fields."""
        msg = Message(
            role="user",
            content="Hello",
            timestamp="2024-01-01T12:00:00"
        )
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "Hello")
        self.assertIsNone(msg.sources)

    def test_message_with_sources(self):
        """Message with optional sources."""
        msg = Message(
            role="assistant",
            content="Response",
            timestamp="2024-01-01T12:00:00",
            sources=[{"chunk_id": "abc123", "score": 0.95}]
        )
        self.assertEqual(len(msg.sources), 1)
        self.assertEqual(msg.sources[0]["chunk_id"], "abc123")

    def test_missing_required_field(self):
        """Error if required field missing."""
        with self.assertRaises(ValidationError):
            Message(role="user", content="Hello")  # missing timestamp


class TestConversation(unittest.TestCase):
    """Tests for Conversation model."""

    def test_valid_conversation(self):
        """Valid conversation."""
        conv = Conversation(
            id="abc123",
            title="Test conversation",
            created_at="2024-01-01T12:00:00",
            updated_at="2024-01-01T12:00:00"
        )
        self.assertEqual(conv.id, "abc123")
        self.assertEqual(conv.messages, [])

    def test_conversation_with_messages(self):
        """Conversation with messages."""
        conv = Conversation(
            id="abc123",
            title="Test",
            created_at="2024-01-01T12:00:00",
            updated_at="2024-01-01T12:00:00",
            messages=[
                Message(
                    role="user",
                    content="Hello",
                    timestamp="2024-01-01T12:00:00"
                )
            ]
        )
        self.assertEqual(len(conv.messages), 1)


class TestChatRequest(unittest.TestCase):
    """Tests for ChatRequest model."""

    def test_minimal_request(self):
        """ChatRequest with only required message."""
        req = ChatRequest(message="Hello")
        self.assertEqual(req.message, "Hello")
        self.assertIsNone(req.conversation_id)
        self.assertIsNone(req.model)
        self.assertTrue(req.use_reranking)
        self.assertTrue(req.use_hybrid)
        self.assertTrue(req.expand_context)

    def test_full_request(self):
        """ChatRequest with all fields."""
        req = ChatRequest(
            message="Question?",
            conversation_id="abc123",
            model="qwen3:latest",
            participant_filter="Alice",
            year_filter=2024,
            date_start="2024-01-01",
            date_end="2024-12-31",
            use_reranking=False,
            use_hybrid=False,
            expand_context=False
        )
        self.assertEqual(req.participant_filter, "Alice")
        self.assertEqual(req.year_filter, 2024)
        self.assertFalse(req.use_reranking)


class TestConversationCreate(unittest.TestCase):
    """Tests for ConversationCreate model."""

    def test_empty_create(self):
        """ConversationCreate without title."""
        data = ConversationCreate()
        self.assertIsNone(data.title)

    def test_with_title(self):
        """ConversationCreate with title."""
        data = ConversationCreate(title="My conversation")
        self.assertEqual(data.title, "My conversation")


class TestTitleEvaluationRequest(unittest.TestCase):
    """Tests for TitleEvaluationRequest model."""

    def test_minimal_request(self):
        """TitleEvaluationRequest with message only."""
        req = TitleEvaluationRequest(message="First message")
        self.assertEqual(req.message, "First message")
        self.assertIsNone(req.model)

    def test_with_model(self):
        """TitleEvaluationRequest with model."""
        req = TitleEvaluationRequest(message="Test", model="llama3:8b")
        self.assertEqual(req.model, "llama3:8b")


if __name__ == '__main__':
    unittest.main()