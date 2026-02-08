"""
Parser for Instagram conversation exports.
"""
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from rag_pipeline.core.models import Message

class InstagramParser:
    """Parses Instagram conversation files."""
    
    def __init__(self):
        self.timestamp_pattern = re.compile(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.+?):')

    def parse_file(self, file_path: Path) -> Tuple[Dict, List[Message]]:
        """Parses a conversation file and extracts metadata and messages."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Extract metadata from header
        metadata = {
            'conversation_id': file_path.stem,
            'file_source': file_path.name,
            'participants': [],
            'title': '',
        }
        
        header_end = 0
        for i, line in enumerate(lines):
            # Keep header parsing logic in French as dataset is French
            if line.startswith('# Conversation Instagram avec'):
                metadata['title'] = line.replace('# Conversation Instagram avec', '').strip()
            elif line.startswith('ID:'):
                metadata['conversation_id'] = line.split(':')[1].strip()
            elif line.startswith('Participants:'):
                participants_str = line.replace('Participants:', '').strip()
                metadata['participants'] = [p.strip() for p in participants_str.split(',')]
            elif line.startswith('=' * 10):
                header_end = i + 1
                break
        
        # Parse messages
        messages = []
        current_message = None
        current_content_lines = []
        
        for line in lines[header_end:]:
            match = self.timestamp_pattern.match(line)
            
            if match:
                # Save previous message
                if current_message is not None:
                    current_message.content = '\n'.join(current_content_lines).strip()
                    if current_message.content or current_message.has_media:
                        messages.append(current_message)
                
                # New message
                timestamp_str = match.group(1)
                author = match.group(2)
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                
                current_message = Message(
                    timestamp=timestamp,
                    author=author,
                    content='',
                    has_media=False
                )
                current_content_lines = []
            elif current_message is not None:
                # Message content
                if line.startswith('📷'):
                    current_message.has_media = True
                    current_message.media_type = 'photo'
                elif line.startswith('🎥'):
                    current_message.has_media = True
                    current_message.media_type = 'video'
                elif line.startswith('🎵'):
                    current_message.has_media = True
                    current_message.media_type = 'audio'
                elif line.startswith('🔗'):
                    current_message.has_media = True
                    current_message.media_type = 'link'
                    current_content_lines.append(line)
                elif not line.startswith('❤️ Réactions:'):
                    current_content_lines.append(line)
        
        # Last message
        if current_message is not None:
            current_message.content = '\n'.join(current_content_lines).strip()
            if current_message.content or current_message.has_media:
                messages.append(current_message)
        
        return metadata, messages