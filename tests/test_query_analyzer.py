"""
Tests pour le module query_analyzer.py
Analyseur de requêtes consolidé (Omni-Prompt).
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
        """Helper pour créer une réponse Ollama mockée"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": json.dumps(content)}
        }
        return mock_response

    # --- Tests mode detection ---
    @patch('requests.post')
    def test_analyze_retrieval_mode(self, mock_post):
        """Mode retrieval détecté pour une question de recherche"""
        mock_post.return_value = self._mock_ollama_response({
            "mode": "retrieval",
            "rewritten_query": "Qui est Ayoub dans mes conversations",
            "intent": "specific_fact",
            "date_range": None
        })
        
        result = self.analyzer.analyze("C'est qui Ayoub ?", [])
        
        self.assertEqual(result.mode, "retrieval")
        self.assertEqual(result.intent, "specific_fact")
        self.assertIsInstance(result, AnalysisResult)

    @patch('requests.post')
    def test_analyze_analytics_mode(self, mock_post):
        """Mode analytics détecté pour une question de comptage"""
        mock_post.return_value = self._mock_ollama_response({
            "mode": "analytics",
            "rewritten_query": "Compter le nombre total de messages",
            "intent": "specific_fact",
            "date_range": None
        })
        
        result = self.analyzer.analyze("Combien j'ai de messages ?", [])
        
        self.assertEqual(result.mode, "analytics")

    # --- Tests date extraction ---
    @patch('requests.post')
    def test_analyze_date_extraction(self, mock_post):
        """Extraction correcte des dates"""
        mock_post.return_value = self._mock_ollama_response({
            "mode": "retrieval",
            "rewritten_query": "Conversations de l'été dernier",
            "intent": "broad_summary",
            "date_range": {"start": "2025-06-01", "end": "2025-08-31"}
        })
        
        result = self.analyzer.analyze("Qu'est-ce qu'on a fait l'été dernier ?", [])
        
        self.assertEqual(result.date_start, "2025-06-01")
        self.assertEqual(result.date_end, "2025-08-31")

    @patch('requests.post')
    def test_analyze_ignores_vague_dates(self, mock_post):
        """Les dates vagues (YYYY-01-01) sont ignorées"""
        mock_post.return_value = self._mock_ollama_response({
            "mode": "retrieval",
            "rewritten_query": "Question sans date particulière",
            "intent": "complex_reasoning",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"}
        })
        
        result = self.analyzer.analyze("De quoi on a parlé ?", [])
        
        # Les dates vagues devraient être ignorées
        self.assertIsNone(result.date_start)
        self.assertIsNone(result.date_end)

    # --- Tests query rewriting ---
    @patch('requests.post')
    def test_analyze_rewrites_query(self, mock_post):
        """La requête est reformulée"""
        mock_post.return_value = self._mock_ollama_response({
            "mode": "retrieval",
            "rewritten_query": "Informations sur le voyage au Maroc avec Ayoub",
            "intent": "broad_summary",
            "date_range": None
        })
        
        history = [
            {"role": "user", "content": "Parle-moi de mon ami Ayoub"},
            {"role": "assistant", "content": "Ayoub est un ami proche..."}
        ]
        
        result = self.analyzer.analyze("Et le voyage au Maroc ?", history)
        
        self.assertIn("voyage", result.rewritten_query.lower())
        self.assertIn("maroc", result.rewritten_query.lower())

    # --- Tests intent to params mapping ---
    def test_get_params_for_specific_fact(self):
        """Paramètres optimisés pour specific_fact"""
        params = self.analyzer._get_params_for_intent("specific_fact")
        
        self.assertEqual(params["top_k"], 5)
        self.assertTrue(params["use_reranking"])
        self.assertFalse(params["expand_context"])

    def test_get_params_for_broad_summary(self):
        """Paramètres optimisés pour broad_summary"""
        params = self.analyzer._get_params_for_intent("broad_summary")
        
        self.assertEqual(params["top_k"], 15)
        self.assertFalse(params["use_reranking"])  # Trop de docs
        self.assertTrue(params["expand_context"])

    def test_get_params_for_complex_reasoning(self):
        """Paramètres optimisés pour complex_reasoning"""
        params = self.analyzer._get_params_for_intent("complex_reasoning")
        
        self.assertEqual(params["top_k"], 10)
        self.assertTrue(params["use_reranking"])
        self.assertTrue(params["expand_context"])

    # --- Tests fallback ---
    @patch('requests.post')
    def test_analyze_fallback_on_error(self, mock_post):
        """Fallback vers paramètres par défaut en cas d'erreur"""
        mock_post.side_effect = Exception("Connection error")
        
        result = self.analyzer.analyze("Ma question", [])
        
        # Fallback avec valeurs par défaut
        self.assertEqual(result.mode, "retrieval")
        self.assertEqual(result.intent, "complex_reasoning")
        self.assertEqual(result.rewritten_query, "Ma question")  # Query non modifiée

    @patch('requests.post')
    def test_analyze_handles_invalid_json(self, mock_post):
        """Gestion du JSON invalide"""
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
        """AnalysisResult a des valeurs par défaut correctes"""
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
