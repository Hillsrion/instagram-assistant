import unittest
from unittest.mock import MagicMock, patch
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.chat import ChatBot
from rag_pipeline.config import Config

class TestTitleEvaluation(unittest.TestCase):

    def setUp(self):
        self.config = Config()
        self.chatbot = ChatBot(config=self.config)

    def test_chatbot_evaluate_title(self):
        mock_response = {"message": {"content": "Vacances a la plage"}}

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            title = self.chatbot.evaluate_title("On part quand a la plage cet ete ?")
            
            self.assertEqual(title, "Vacances a la plage")


from fastapi.testclient import TestClient
from app import app

class TestTitleEvaluationIntegration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_endpoint_evaluate_title(self):
        mock_title = "Projet de voyage"
        with patch("app.chatbot") as mock_chatbot:
            mock_chatbot.evaluate_title.return_value = mock_title
            response = self.client.post("/api/evaluate-title", json={"message": "On devrait organiser notre voyage en Italie."})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"title": mock_title})

    def test_endpoint_evaluate_title_no_chatbot(self):
        with patch("app.chatbot", None):
            response = self.client.post("/api/evaluate-title", json={"message": "Hello"})
            self.assertEqual(response.status_code, 503)
if __name__ == "__main__":
    unittest.main()