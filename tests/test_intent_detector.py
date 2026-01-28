"""
Tests pour le module intent_detector.py
Détection d'intention pour optimiser les paramètres du RAG.
"""
import unittest
from unittest.mock import patch, MagicMock

from rag_pipeline.config import Config
from rag_pipeline.intent_detector import IntentDetector, SearchIntent


class TestIntentDetector(unittest.TestCase):

    def setUp(self):
        self.config = Config()
        self.detector = IntentDetector(self.config)

    def _mock_ollama_response(self, intent_str: str):
        """Helper pour créer une réponse Ollama mockée"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": intent_str}
        }
        return mock_response

    # --- Tests de détection d'intention ---
    @patch('requests.post')
    def test_detect_specific_fact(self, mock_post):
        """Détection intention specific_fact"""
        mock_post.return_value = self._mock_ollama_response("specific_fact")
        
        result = self.detector.detect_intent("Quel jour on s'est rencontrés ?")
        
        self.assertEqual(result["intent"], SearchIntent.SPECIFIC_FACT)
        self.assertEqual(result["top_k"], 3)  # Peu de résultats pour fait précis
        self.assertTrue(result["use_reranking"])
        self.assertFalse(result["expand_context"])

    @patch('requests.post')
    def test_detect_broad_summary(self, mock_post):
        """Détection intention broad_summary"""
        mock_post.return_value = self._mock_ollama_response("broad_summary")
        
        result = self.detector.detect_intent("De quoi on a parlé ces derniers mois ?")
        
        self.assertEqual(result["intent"], SearchIntent.BROAD_SUMMARY)
        self.assertEqual(result["top_k"], 12)  # Beaucoup de résultats
        self.assertFalse(result["use_reranking"])  # Trop de docs
        self.assertTrue(result["expand_context"])

    @patch('requests.post')
    def test_detect_complex_reasoning(self, mock_post):
        """Détection intention complex_reasoning"""
        mock_post.return_value = self._mock_ollama_response("complex_reasoning")
        
        result = self.detector.detect_intent("Quelle est la relation entre Marie et Paul ?")
        
        self.assertEqual(result["intent"], SearchIntent.COMPLEX_REASONING)
        self.assertEqual(result["top_k"], 8)
        self.assertTrue(result["use_reranking"])
        self.assertTrue(result["expand_context"])

    # --- Tests de fallback ---
    @patch('requests.post')
    def test_fallback_on_connection_error(self, mock_post):
        """Fallback si erreur de connexion"""
        mock_post.side_effect = Exception("Connection refused")
        
        result = self.detector.detect_intent("Ma question")
        
        self.assertIsNone(result["intent"])
        self.assertEqual(result["top_k"], self.config.top_k)
        self.assertTrue(result["use_reranking"])
        self.assertIn("error", result)

    @patch('requests.post')
    def test_fallback_on_unknown_intent(self, mock_post):
        """Fallback si intention non reconnue"""
        mock_post.return_value = self._mock_ollama_response("unknown_category")
        
        result = self.detector.detect_intent("Question bizarre")
        
        # Fallback vers complex_reasoning
        self.assertEqual(result["intent"], SearchIntent.COMPLEX_REASONING)
        self.assertEqual(result["top_k"], self.config.top_k)

    @patch('requests.post')
    def test_fallback_on_timeout(self, mock_post):
        """Fallback si timeout"""
        from requests.exceptions import Timeout
        mock_post.side_effect = Timeout("Request timed out")
        
        result = self.detector.detect_intent("Question")
        
        self.assertIsNone(result["intent"])
        self.assertIn("error", result)

    # --- Tests de robustesse ---
    @patch('requests.post')
    def test_handles_intent_with_whitespace(self, mock_post):
        """Gestion des espaces dans la réponse"""
        mock_post.return_value = self._mock_ollama_response("  specific_fact  \n")
        
        result = self.detector.detect_intent("Question précise")
        
        self.assertEqual(result["intent"], SearchIntent.SPECIFIC_FACT)

    @patch('requests.post')
    def test_handles_intent_mixed_case(self, mock_post):
        """Gestion des majuscules dans la réponse"""
        mock_post.return_value = self._mock_ollama_response("BROAD_SUMMARY")
        
        result = self.detector.detect_intent("Question large")
        
        self.assertEqual(result["intent"], SearchIntent.BROAD_SUMMARY)


class TestSearchIntent(unittest.TestCase):
    
    def test_search_intent_values(self):
        """Les valeurs de SearchIntent sont correctes"""
        self.assertEqual(SearchIntent.SPECIFIC_FACT.value, "specific_fact")
        self.assertEqual(SearchIntent.BROAD_SUMMARY.value, "broad_summary")
        self.assertEqual(SearchIntent.COMPLEX_REASONING.value, "complex_reasoning")

    def test_search_intent_is_string_enum(self):
        """SearchIntent est une string enum"""
        self.assertIsInstance(SearchIntent.SPECIFIC_FACT, str)


if __name__ == '__main__':
    unittest.main()
