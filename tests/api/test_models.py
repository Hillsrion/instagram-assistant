"""
Tests pour les modèles Pydantic de l'API.
"""
import unittest
from pydantic import ValidationError

from api.models import Message, Conversation, ChatRequest, ConversationCreate, TitleEvaluationRequest


class TestMessage(unittest.TestCase):
    """Tests pour le modèle Message."""

    def test_valid_message(self):
        """Message valide avec tous les champs requis."""
        msg = Message(
            role="user",
            content="Hello",
            timestamp="2024-01-01T12:00:00"
        )
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "Hello")
        self.assertIsNone(msg.sources)

    def test_message_with_sources(self):
        """Message avec sources optionnelles."""
        msg = Message(
            role="assistant",
            content="Response",
            timestamp="2024-01-01T12:00:00",
            sources=[{"chunk_id": "abc123", "score": 0.95}]
        )
        self.assertEqual(len(msg.sources), 1)
        self.assertEqual(msg.sources[0]["chunk_id"], "abc123")

    def test_missing_required_field(self):
        """Erreur si champ requis manquant."""
        with self.assertRaises(ValidationError):
            Message(role="user", content="Hello")  # timestamp manquant


class TestConversation(unittest.TestCase):
    """Tests pour le modèle Conversation."""

    def test_valid_conversation(self):
        """Conversation valide."""
        conv = Conversation(
            id="abc123",
            title="Test conversation",
            created_at="2024-01-01T12:00:00",
            updated_at="2024-01-01T12:00:00"
        )
        self.assertEqual(conv.id, "abc123")
        self.assertEqual(conv.messages, [])

    def test_conversation_with_messages(self):
        """Conversation avec messages."""
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
    """Tests pour le modèle ChatRequest."""

    def test_minimal_request(self):
        """ChatRequest avec seulement le message requis."""
        req = ChatRequest(message="Bonjour")
        self.assertEqual(req.message, "Bonjour")
        self.assertIsNone(req.conversation_id)
        self.assertIsNone(req.model)
        self.assertTrue(req.use_reranking)
        self.assertTrue(req.use_hybrid)
        self.assertTrue(req.expand_context)

    def test_full_request(self):
        """ChatRequest avec tous les champs."""
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
    """Tests pour le modèle ConversationCreate."""

    def test_empty_create(self):
        """ConversationCreate sans titre."""
        data = ConversationCreate()
        self.assertIsNone(data.title)

    def test_with_title(self):
        """ConversationCreate avec titre."""
        data = ConversationCreate(title="Ma conversation")
        self.assertEqual(data.title, "Ma conversation")


class TestTitleEvaluationRequest(unittest.TestCase):
    """Tests pour le modèle TitleEvaluationRequest."""

    def test_minimal_request(self):
        """TitleEvaluationRequest avec message seulement."""
        req = TitleEvaluationRequest(message="Premier message")
        self.assertEqual(req.message, "Premier message")
        self.assertIsNone(req.model)

    def test_with_model(self):
        """TitleEvaluationRequest avec modèle."""
        req = TitleEvaluationRequest(message="Test", model="llama3:8b")
        self.assertEqual(req.model, "llama3:8b")


if __name__ == '__main__':
    unittest.main()
