"""
Tests for intent_detector.py module.
Intent detection for RAG optimization.
"""
import unittest
from unittest.mock import patch, MagicMock

from rag_pipeline.core.config import Config
from rag_pipeline.query.intent_detector import IntentDetector, SearchIntent


class TestIntentDetector(unittest.TestCase):

    def setUp(self):
        self.config = Config()
        self.detector = IntentDetector(self.config)

    def _mock_ollama_response(self, intent_str: str):
        """Helper to create a mocked Ollama response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": intent_str}
        }
        return mock_response

    # --- Tests intent detection ---
    @patch('requests.post')
    def test_detect_specific_fact(self, mock_post):
        """Detect specific_fact intent."""
        mock_post.return_value = self._mock_ollama_response("specific_fact")
        
        result = self.detector.detect_intent("What day did we meet?")
        
        self.assertEqual(result["intent"], SearchIntent.SPECIFIC_FACT)
        self.assertEqual(result["top_k"], 3)  # Few results for precise fact
        self.assertTrue(result["use_reranking"])
        self.assertFalse(result["expand_context"])

    @patch('requests.post')
    def test_detect_broad_summary(self, mock_post):
        """Detect broad_summary intent."""
        mock_post.return_value = self._mock_ollama_response("broad_summary")
        
        result = self.detector.detect_intent("What did we talk about last month?")
        
        self.assertEqual(result["intent"], SearchIntent.BROAD_SUMMARY)
        self.assertEqual(result["top_k"], 12)  # Many results
        self.assertFalse(result["use_reranking"])  # Too many docs
        self.assertTrue(result["expand_context"])

    @patch('requests.post')
    def test_detect_complex_reasoning(self, mock_post):
        """Detect complex_reasoning intent."""
        mock_post.return_value = self._mock_ollama_response("complex_reasoning")
        
        result = self.detector.detect_intent("What is the relationship between Marie and Paul?")
        
        self.assertEqual(result["intent"], SearchIntent.COMPLEX_REASONING)
        self.assertEqual(result["top_k"], 8)
        self.assertTrue(result["use_reranking"])
        self.assertTrue(result["expand_context"])

    # --- Tests fallback ---
    @patch('requests.post')
    def test_fallback_on_connection_error(self, mock_post):
        """Fallback on connection error."""
        mock_post.side_effect = Exception("Connection refused")
        
        result = self.detector.detect_intent("My question")
        
        self.assertIsNone(result["intent"])
        self.assertEqual(result["top_k"], self.config.top_k)
        self.assertTrue(result["use_reranking"])
        self.assertIn("error", result)

    @patch('requests.post')
    def test_fallback_on_unknown_intent(self, mock_post):
        """Fallback on unknown intent."""
        mock_post.return_value = self._mock_ollama_response("unknown_category")
        
        result = self.detector.detect_intent("Weird question")
        
        # Fallback to complex_reasoning
        self.assertEqual(result["intent"], SearchIntent.COMPLEX_REASONING)
        self.assertEqual(result["top_k"], self.config.top_k)

    @patch('requests.post')
    def test_fallback_on_timeout(self, mock_post):
        """Fallback on timeout."""
        from requests.exceptions import Timeout
        mock_post.side_effect = Timeout("Request timed out")
        
        result = self.detector.detect_intent("Question")
        
        self.assertIsNone(result["intent"])
        self.assertIn("error", result)

    # --- Tests robustness ---
    @patch('requests.post')
    def test_handles_intent_with_whitespace(self, mock_post):
        """Handles whitespace in response."""
        mock_post.return_value = self._mock_ollama_response("  specific_fact  \n")
        
        result = self.detector.detect_intent("Precise question")
        
        self.assertEqual(result["intent"], SearchIntent.SPECIFIC_FACT)

    @patch('requests.post')
    def test_handles_intent_mixed_case(self, mock_post):
        """Handles mixed case in response."""
        mock_post.return_value = self._mock_ollama_response("BROAD_SUMMARY")
        
        result = self.detector.detect_intent("Broad question")
        
        self.assertEqual(result["intent"], SearchIntent.BROAD_SUMMARY)


class TestSearchIntent(unittest.TestCase):
    
    def test_search_intent_values(self):
        """SearchIntent values are correct."""
        self.assertEqual(SearchIntent.SPECIFIC_FACT.value, "specific_fact")
        self.assertEqual(SearchIntent.BROAD_SUMMARY.value, "broad_summary")
        self.assertEqual(SearchIntent.COMPLEX_REASONING.value, "complex_reasoning")

    def test_search_intent_is_string_enum(self):
        """SearchIntent is a string enum."""
        self.assertIsInstance(SearchIntent.SPECIFIC_FACT, str)


if __name__ == '__main__':
    unittest.main()