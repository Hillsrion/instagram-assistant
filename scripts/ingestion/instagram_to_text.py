#!/usr/bin/env python3
"""
Instagram JSON to Text Converter.

Converts Instagram conversation exports (JSON) into the text format
expected by the RAG pipeline.

Integrates Audio Transcription via VLLM/Voxtral if enabled.
"""
import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from threading import Lock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.core.config import Config, default_config
from rag_pipeline.audio.audio import AudioTranscriber
from rag_pipeline.core.logger import initialize_logging, logger

# Helper to decode latin-1 stuck in utf-8 (common Instagram export issue)
def decode_instagram_text(text: str) -> str:
    if not text:
        return ""
    try:
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

def ms_to_datetime(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000.0).strftime('%Y-%m-%d %H:%M:%S')

def process_conversation(json_path: Path, output_dir: Path, transcriber: AudioTranscriber, config: Config):
    """Processes a single conversation JSON file."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {json_path}: {e}")
        return

    # Extract Metadata
    participants_raw = data.get('participants', [])
    participants = [decode_instagram_text(p.get('name', 'User')) for p in participants_raw]
    title = decode_instagram_text(data.get('title', 'Conversation'))
    
    messages = data.get('messages', [])
    if not messages:
        return

    # Sort chronological (oldest first) - Instagram exports are often reverse chronological
    messages.sort(key=lambda x: x.get('timestamp_ms', 0))

    # Stats
    media_count = 0
    audio_count = 0
    transcribed_count = 0 
    
    # Prepare output content
    output_lines = []
    
    # Header
    conv_id = json_path.parent.name
    first_date = ms_to_datetime(messages[0].get('timestamp_ms', 0))
    last_date = ms_to_datetime(messages[-1].get('timestamp_ms', 0))

    output_lines.append(f"# Conversation Instagram avec {title}")
    output_lines.append(f"ID: {conv_id}")
    output_lines.append(f"Nombre de messages: {len(messages)}")
    output_lines.append(f"Période: du {first_date} au {last_date}")
    output_lines.append(f"Participants: {', '.join(participants)}")
    output_lines.append("\n" + "="*10 + "\n")

    # Process messages
    for msg in messages:
        sender = decode_instagram_text(msg.get('sender_name', 'Unknown'))
        timestamp = ms_to_datetime(msg.get('timestamp_ms', 0))
        content = decode_instagram_text(msg.get('content', ''))
        
        # Build message block
        output_lines.append(f"[{timestamp}] {sender}:")
        
        has_content = False
        
        # 1. Text Content
        if content:
            output_lines.append(content)
            has_content = True
        
        # 2. Photos/Videos
        if 'photos' in msg:
            output_lines.append("📷 [Photo]")
            has_content = True
        if 'videos' in msg:
            output_lines.append("🎥 [Video]")
            has_content = True
            
        # 3. Audio
        if 'audio_files' in msg:
            audio_count += 1
            output_lines.append("🎵") # Indicator for chunker
            has_content = True
            
            # Transcription logic
            if config.enable_audio_transcription:
                for audio_item in msg['audio_files']:
                    # URI is relative to the export root usually, e.g. "your_instagram_activity/..."
                    # Check if audio file exists relative to json_path's export root?
                    # The json_path is deep inside: .../messages/inbox/ID/message_1.json
                    # The URI is usually relative to the "export root".
                    
                    # We need to find the export root relative to the json file.
                    # JSON is at: .../your_instagram_activity/messages/inbox/{ID}/
                    # URI starts with: your_instagram_activity/...
                    
                    # So we need to go up 4 levels from message_1.json to get export root?
                    # json_path.parent = {ID}
                    # json_path.parent.parent = inbox
                    # json_path.parent.parent.parent = messages
                    # json_path.parent.parent.parent.parent = your_instagram_activity (Wait, URI starts with this)
                    # So export root is parent of your_instagram_activity?
                    
                    # Let's try to resolve the path.
                    # Standard Export Structure:
                    # ROOT/
                    #   your_instagram_activity/
                    #     messages/
                    #       inbox/
                    #         {ID}/
                    #           message_1.json
                    #           audio/
                    #             file.mp4
                    
                    # The URI in JSON: "your_instagram_activity/messages/inbox/{ID}/audio/file.mp4"
                    
                    # So absolute path = ROOT / URI
                    # JSON Path = ROOT / your_instagram_activity / messages / inbox / {ID} / message_1.json
                    
                    # We can find ROOT by going up from JSON Path until we find the parent of 'your_instagram_activity'
                    # Or simpler: The audio folder usually is a sibling of message_1.json?
                    
                    # Let's look at URI basename.
                    audio_uri = audio_item.get('uri', '')
                    audio_filename = os.path.basename(audio_uri)
                    
                    # Check if 'audio' folder exists next to json file
                    local_audio_path = json_path.parent / "audio" / audio_filename
                    
                    if local_audio_path.exists():
                        print(f"   🎙️  Transcribing {local_audio_path.name}...")
                        text = transcriber.transcribe(local_audio_path)
                        if text:
                            output_lines.append(f"(Transcription audio: \"{text}\")")
                            transcribed_count += 1
                        else:
                             output_lines.append("(Transcription impossible)")
                    else:
                        # Fallback: try to find it via full uri logic if possible (e.g. if we are in a merged folder structure)
                        # But typically 'audio' is adjacent in modern exports or merged folders
                        logger.debug(f"Audio file not found at {local_audio_path}")
                        output_lines.append("(Audio non trouvé)")

        # 4. Links/Share
        if 'share' in msg and 'link' in msg['share']:
            link = msg['share']['link']
            output_lines.append(f"🔗 {link}")
            has_content = True
            
        # Empty message fallback
        if not has_content:
            output_lines.pop() # Remove header line [Date]...
        else:
            output_lines.append("") # Empty line after message
            
    # Write to file
    output_filename = f"{conv_id}.txt"
    # Use participant names if available for filename? 
    # Can be messy with emojis, keep ID for safety or "Name_ID.txt"
    safe_title = "".join([c if c.isalnum() else "_" for c in title])[:50]
    output_filename = f"{safe_title}_{conv_id}.txt"
    
    out_file = output_dir / output_filename
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(output_lines))
        
    print(f"✅ Converted {conv_id} ({len(messages)} msgs, {audio_count} audios)")


def main():
    parser = argparse.ArgumentParser(description="Convert Instagram JSON to RAG-ready Text.")
    parser.add_argument("--source", type=Path, help="Path to 'original_import_folders' or specific export dir")
    parser.add_argument("--output", type=Path, help="Output directory for .txt files")
    parser.add_argument("--limit", type=int, help="Limit number of conversations")
    args = parser.parse_args()
    
    config = Config()
    
    # 1. Setup Logic
    source_dir = args.source or Path("original_import_folders")
    output_dir = args.output or config.conversations_dir
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    transcriber = AudioTranscriber()
    if config.enable_audio_transcription:
        print(f"🔊 Audio Transcription ENABLED (URL: {config.vllm_audio_url})")
    else:
        print("Duplicate/Test Run? Audio disabled via config.")

    # 2. Find all message_1.json files
    print(f"🔍 Scanning {source_dir}...")
    json_files = sorted(source_dir.glob("**/message_1.json"))
    
    if args.limit:
        json_files = json_files[:args.limit]
        
    print(f"Found {len(json_files)} conversations.")
    
    # 3. Process
    for i, json_file in enumerate(json_files):
        process_conversation(json_file, output_dir, transcriber, config)
        
    print("\n🎉 Conversion complete.")

if __name__ == "__main__":
    main()