import unittest
import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from rag_pipeline.audio import AudioTranscriber
from rag_pipeline.config import Config
from instagram_to_text import process_conversation

class TestAudioIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("temp_test_audio")
        self.test_dir.mkdir(exist_ok=True)
        
        # Setup fake conversation structure
        self.conv_id = "123456789"
        self.conv_inbox = self.test_dir / "your_instagram_activity" / "messages" / "inbox" / self.conv_id
        self.conv_inbox.mkdir(parents=True, exist_ok=True)
        
        self.audio_dir = self.conv_inbox / "audio"
        self.audio_dir.mkdir(exist_ok=True)
        
        # Fake audio file
        self.audio_file = self.audio_dir / "test_audio.mp4"
        self.audio_file.touch()
        
        # Fake message_1.json
        self.message_json = self.conv_inbox / "message_1.json"
        data = {
            "participants": [{"name": "UserA"}, {"name": "UserB"}],
            "messages": [
                {
                    "sender_name": "UserA",
                    "timestamp_ms": 1600000000000,
                    "content": "Listen to this",
                    "audio_files": [
                        {"uri": f"your_instagram_activity/messages/inbox/{self.conv_id}/audio/test_audio.mp4"}
                    ]
                }
            ],
            "title": "Test Chat"
        }
        with open(self.message_json, "w", encoding="utf-8") as f:
            json.dump(data, f)
            
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("rag_pipeline.audio.requests.post")
    def test_transcription_called(self, mock_post):
        # Mock VLLM response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "This is a transcribed text"}}]
        }
        mock_post.return_value = mock_response
        
        # Setup Config
        config = Config()
        config.enable_audio_transcription = True
        config.vllm_audio_url = "http://fake-url"
        
        transcriber = AudioTranscriber(api_url="http://fake-url")
        transcriber.enabled = True # Force enable for test
        
        # Run process
        process_conversation(self.message_json, self.output_dir, transcriber, config)
        
        # Check output file
        output_file = list(self.output_dir.glob("*.txt"))[0]
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
            
        print("Generated Content:\n", content)
        
        self.assertIn("🎵", content)
        self.assertIn('(Transcription audio: "This is a transcribed text")', content)
        
        # Verify Mock Call
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("http://fake-url/chat/completions", args[0])

if __name__ == "__main__":
    unittest.main()
