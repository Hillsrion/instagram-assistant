"""
Tests for query_analyzer.py module.
Consolidated Query Analyzer (Omni-Prompt).
"""
import unittest
import json
from unittest.mock import patch, MagicMock

from rag_pipeline.config import Config
from rag_pipeline.query_analyzer import QueryAnalyzer, AnalysisResult


class TestQueryAnalyzer(unittest.TestCase):

    def setUp(self):
        self.config = Config()
        self.analyzer = QueryAnalyzer(self.config)

    def _mock_ollama_response(self, content: dict):
        """Helper to create a mocked Ollama response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": json.dumps(content)}
        }
        return mock_response

    # --- Tests mode detection ---
    @patch('requests.post')
    def test_analyze_retrieval_mode(self, mock_post):
        """Retrieval mode detected for a research question."""
        mock_post.return_value = self._mock_ollama_response({
            "mode": "retrieval",
            "rewritten_query": "Who is Ayoub in my conversations",
            "intent": "specific_fact",
            "date_range": None
        })
        
        result = self.analyzer.analyze("Who is Ayoub?", [])
        
        self.assertEqual(result.mode, "retrieval")
        self.assertEqual(result.intent, "specific_fact")
        self.assertIsInstance(result, AnalysisResult)

    @patch('requests.post')
    def test_analyze_analytics_mode(self, mock_post):
        """Analytics mode detected for a counting question."""
        mock_post.return_value = self._mock_ollama_response({
            "mode": "analytics",
            "rewritten_query": "Count total number of messages",
            "intent": "specific_fact",
            "date_range": None
        })
        
        result = self.analyzer.analyze("How many messages do I have?", [])
        
        self.assertEqual(result.mode, "analytics")

    # --- Tests date extraction ---
    @patch('requests.post')
    def test_analyze_date_extraction(self, mock_post):
        """Correct extraction of dates."""
        mock_post.return_value = self._mock_ollama_response({
            "mode": "retrieval",
            "rewritten_query": "Conversations from last summer",
            "intent": "broad_summary",
            "date_range": {"start": "2025-06-01", "end": "2025-08-31"}
        })
        
        result = self.analyzer.analyze("What did we do last summer?", [])
        
        self.assertEqual(result.date_start, "2025-06-01")
        self.assertEqual(result.date_end, "2025-08-31")

    @patch('requests.post')
    def test_analyze_ignores_vague_dates(self, mock_post):
        """Vague dates (YYYY-01-01) are ignored."""
        mock_post.return_value = self._mock_ollama_response({
            "mode": "retrieval",
            "rewritten_query": "Question without specific date",
            "intent": "complex_reasoning",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"}
        })
        
        result = self.analyzer.analyze("What did we talk about?", [])
        
        # Vague dates should be ignored
        self.assertIsNone(result.date_start)
        self.assertIsNone(result.date_end)

    # --- Tests query rewriting ---
    @patch('requests.post')
    def test_analyze_rewrites_query(self, mock_post):
        """Query is rewritten."""
        mock_post.return_value = self._mock_ollama_response({
            "mode": "retrieval",
            "rewritten_query": "Information about the trip to Morocco with Ayoub",
            "intent": "broad_summary",
            "date_range": None
        })
        
        history = [
            {"role": "user", "content": "Tell me about my friend Ayoub"},
            {"role": "assistant", "content": "Ayoub is a close friend..."}
        ]
        
        result = self.analyzer.analyze("And the trip to Morocco?", history)
        
        self.assertIn("trip", result.rewritten_query.lower())
        self.assertIn("morocco", result.rewritten_query.lower())

    # --- Tests intent to params mapping ---
    def test_get_params_for_specific_fact(self):
        """Optimized parameters for specific_fact."""
        params = self.analyzer._get_params_for_intent("specific_fact")
        
        self.assertEqual(params["top_k"], 5)
        self.assertTrue(params["use_reranking"])
        self.assertFalse(params["expand_context"])

    def test_get_params_for_broad_summary(self):
        """Optimized parameters for broad_summary."""
        params = self.analyzer._get_params_for_intent("broad_summary")
        
        self.assertEqual(params["top_k"], 15)
        self.assertFalse(params["use_reranking"])  # Too many docs
        self.assertTrue(params["expand_context"])

    def test_get_params_for_complex_reasoning(self):
        """Optimized parameters for complex_reasoning."""
        params = self.analyzer._get_params_for_intent("complex_reasoning")
        
        self.assertEqual(params["top_k"], 10)
        self.assertTrue(params["use_reranking"])
        self.assertTrue(params["expand_context"])

    # --- Tests fallback ---
    @patch('requests.post')
    def test_analyze_fallback_on_error(self, mock_post):
        """Fallback to default parameters on error."""
        mock_post.side_effect = Exception("Connection error")
        
        result = self.analyzer.analyze("My question", [])
        
        # Fallback with default values
        self.assertEqual(result.mode, "retrieval")
        self.assertEqual(result.intent, "complex_reasoning")
        self.assertEqual(result.rewritten_query, "My question")  # Unmodified query

    @patch('requests.post')
    def test_analyze_handles_invalid_json(self, mock_post):
        """Handling of invalid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "not valid json"}
        }
        mock_post.return_value = mock_response
        
        result = self.analyzer.analyze("Test query", [])
        
        # Fallback
        self.assertEqual(result.mode, "retrieval")


class TestAnalysisResult(unittest.TestCase):
    
    def test_analysis_result_defaults(self):
        """AnalysisResult has correct default values."""
        result = AnalysisResult(
            rewritten_query="test",
            intent="simple",
            mode="retrieval",
            top_k=5
        )
        
        self.assertIsNone(result.date_start)
        self.assertIsNone(result.date_end)
        self.assertTrue(result.use_reranking)
        self.assertTrue(result.expand_context)


if __name__ == '__main__':
    unittest.main()