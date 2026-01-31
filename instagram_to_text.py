#!/usr/bin/env python3
"""
Converts Instagram JSON exports to text format for RAG indexing.
Reconstructed based on chunker requirements.
"""
import json
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Fix encoding issues common with Instagram exports
def decode_instagram_text(text: str) -> str:
    if not text:
        return ""
    try:
        return text.encode('latin1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

def get_stats(messages: List[Dict]) -> Dict:
    media_count = 0
    link_count = 0
    reaction_count = 0
    call_count = 0
    
    for msg in messages:
        # Check photos/videos
        if msg.get('photos') or msg.get('videos') or msg.get('audio_files'):
            media_count += 1
        
        # Check links (naive check in content or share)
        content = decode_instagram_text(msg.get('content', ''))
        if 'http' in content:
            link_count += 1
        if msg.get('share'):
            link_count += 1
            
        # Check reactions
        if msg.get('reactions'):
            reaction_count += len(msg['reactions'])
            
        # Check calls
        if msg.get('call_duration'):
            call_count += 1
            
    return {
        'media_count': media_count,
        'link_count': link_count,
        'reaction_count': reaction_count,
        'call_count': call_count
    }

def process_conversation(conv_dir: Path, output_dir: Path) -> bool:
    json_path = conv_dir / "message_1.json"
    if not json_path.exists():
        return False
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {json_path}: {e}")
        return False
        
    participants = data.get('participants', [])
    messages = data.get('messages', [])
    title = decode_instagram_text(data.get('title', conv_dir.name))
    conv_id = conv_dir.name
    
    if not messages:
        return False
        
    # Sort messages by timestamp
    messages.sort(key=lambda x: x.get('timestamp_ms', 0))
    
    # Date range
    first_msg = messages[0].get('timestamp_ms', 0) / 1000
    last_msg = messages[-1].get('timestamp_ms', 0) / 1000
    first_date = datetime.fromtimestamp(first_msg).strftime('%Y-%m-%d')
    last_date = datetime.fromtimestamp(last_msg).strftime('%Y-%m-%d')
    
    stats = get_stats(messages)
    
    # Build text content
    lines = []
    lines.append(f"# Conversation Instagram avec {title}")
    lines.append(f"ID: {conv_id}")
    lines.append(f"Nombre de messages: {len(messages)}")
    lines.append("")
    lines.append(f"Période: du {first_date} au {last_date}")
    lines.append("")
    
    participant_names = [decode_instagram_text(p.get('name', '')) for p in participants]
    lines.append(f"Participants: {', '.join(participant_names)}")
    lines.append("")
    lines.append("Statistiques:")
    lines.append(f"  • Médias partagés: {stats['media_count']}")
    if stats['link_count'] > 0:
        lines.append(f"  • Liens partagés: {stats['link_count']}")
    if stats['reaction_count'] > 0:
        lines.append(f"  • Réactions totales: {stats['reaction_count']}")
    if stats['call_count'] > 0:
        lines.append(f"  • Appels: {stats['call_count']}")
        
    lines.append("")
    lines.append("=" * 10)
    lines.append("")
    
    for msg in messages:
        ts = msg.get('timestamp_ms', 0) / 1000
        dt = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        sender = decode_instagram_text(msg.get('sender_name', 'Unknown'))
        content = decode_instagram_text(msg.get('content', ''))
        
        # Handle media/special types
        if msg.get('photos'):
            content = "[Photo] " + content
        elif msg.get('videos'):
            content = "[Vidéo] " + content
        elif msg.get('audio_files'):
            content = "[Audio] " + content
        elif msg.get('share'):
             content = "[Lien partagé] " + content
             
        # Reactions
        reactions = ""
        if msg.get('reactions'):
            r_list = []
            for r in msg['reactions']:
                emoji = decode_instagram_text(r.get('reaction', ''))
                actor = decode_instagram_text(r.get('actor', ''))
                r_list.append(f"{emoji} ({actor})")
            reactions = f"\n❤️ Réactions: {', '.join(r_list)}"
            
        lines.append(f"[{dt}] {sender}: {content}{reactions}")
        
    # Write to file
    output_path = output_dir / f"{conv_id}.txt"
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return True
    except Exception as e:
        print(f"Error writing {output_path}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Convert Instagram JSON to Text")
    parser.add_argument('--input', type=Path, default=Path('merged_instagram_export'), help='Input directory (JSON)')
    parser.add_argument('--output', type=Path, default=Path('instagram_conversations'), help='Output directory (TXT)')
    
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"Input directory not found: {args.input}")
        # Try default locations
        if Path("original_import_folders").exists():
             print(f"Checking original_import_folders...")
             # Logic to find inbox... but simple usage expects merged or direct inbox
        return

    args.output.mkdir(parents=True, exist_ok=True)
    
    conv_dirs = [d for d in args.input.iterdir() if d.is_dir()]
    print(f"Found {len(conv_dirs)} conversations in {args.input}")
    
    count = 0
    for conv_dir in conv_dirs:
        if process_conversation(conv_dir, args.output):
            count += 1
            if count % 10 == 0:
                print(f"Processed {count} conversations...")
                
    print(f"Done! {count} conversations converted to text in {args.output}")

if __name__ == "__main__":
    main()
