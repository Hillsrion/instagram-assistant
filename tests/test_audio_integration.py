import unittest
import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
# Add scripts/ingestion to path to import the script module
sys.path.append(str(Path(__file__).parent.parent / "scripts" / "ingestion"))

from rag_pipeline.audio import AudioTranscriber
from rag_pipeline.config import Config

# Now we can import the script
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

    @patch("rag_pipeline.audio.default_config")
    @patch("rag_pipeline.audio.MlxAudioProvider")
    def test_transcription_called(self, MockProvider, mock_config):
        # Mock Provider instance
        mock_instance = MockProvider.return_value
        mock_instance.transcribe.return_value = "This is a transcribed text"
        
        # Setup Config Mock
        mock_config.enable_audio_transcription = True
        mock_config.voxtral_language = "fr"
        mock_config.mlx_audio_model = "shreyask/voxtral-mini-4b-realtime-mlx-int4"
        
        # Init without args (will pick up true from mock_config)
        transcriber = AudioTranscriber()
        
        # Create a config object for process_conversation (it expects one)
        config = Config()
        config.enable_audio_transcription = True
        
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
        mock_instance.transcribe.assert_called_once()
        args, kwargs = mock_instance.transcribe.call_args
        # Check if the called path ends with test_audio.mp4
        self.assertTrue(str(args[0]).endswith("test_audio.mp4"))

if __name__ == "__main__":
    unittest.main()
