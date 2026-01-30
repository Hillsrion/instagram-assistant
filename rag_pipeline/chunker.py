"""
Semantic chunker for Instagram conversations.
Splits conversations into temporal chunks with enriched metadata.
"""
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict

from .config import Config, default_config


@dataclass
class Message:
    """An individual message."""
    timestamp: datetime
    author: str
    content: str
    has_media: bool = False
    media_type: Optional[str] = None  # photo, video, audio, link


@dataclass
class Chunk:
    """A conversation chunk with enriched metadata."""
    chunk_id: str
    conversation_id: str
    participants: List[str]
    date_start: str
    date_end: str
    message_count: int
    content: str
    file_source: str
    # New fields for "Gold Standard" RAG
    narrative_summary: Optional[str] = None
    hypothetical_questions: Optional[List[str]] = None
    speaker_intents: Optional[Dict[str, str]] = None
    temporal_context: Optional[str] = None
    emotions: Optional[Dict[str, Any]] = None  # {dominant, tone, tension_level}
    entities: Optional[Dict[str, List[str]]] = None  # {locations: [], people: [], media: [], events: []}
    
    # New "Social" enrichment fields
    interaction_pattern: Optional[str] = None  # e.g. "Planification", "Récit", "Débat"
    initiative: Optional[str] = None  # e.g. "UserA leads", "Balanced"
    emotional_shift: Optional[str] = None  # e.g. "neutral -> happy"
    open_loops: Optional[List[str]] = None  # Unresolved topics
    
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Chunk":
        # Filter out any unknown fields (e.g., 'summary' from old chunks)
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    def get_embedding_text(self) -> str:
        """
        Returns text to encode (Questions + Summary + Content).
        Including hypothetical questions drastically improves retrieval.
        """
        text_parts = []
        
        # 1. Hypothetical questions (High priority for matching)
        if self.hypothetical_questions:
            text_parts.append("Questions answered by this document:")
            text_parts.extend(self.hypothetical_questions)
            text_parts.append("")

        # 2. Semantic temporal context
        if self.temporal_context:
            text_parts.append(f"Period: {self.temporal_context}")
            text_parts.append("")

        # 3. Named Entities (Locations, People, etc.)
        if self.entities:
            text_parts.append("Mentioned entities:")
            for category, items in self.entities.items():
                if items:
                    # Sanitize items to ensure they are strings
                    safe_items = [str(item) for item in items if item]
                    if safe_items:
                        text_parts.append(f"  - {category}: {', '.join(safe_items)}")
            text_parts.append("")

        # 4. Participant intents
        if self.speaker_intents:
            text_parts.append("Participant intents:")
            for participant, intent in self.speaker_intents.items():
                text_parts.append(f"  - {participant} : {intent}")
            text_parts.append("")

        # 5. Emotions (Emotional context)
        if self.emotions:
            emotion_parts = []
            if self.emotions.get("dominant"):
                emotion_parts.append(f"dominant emotion: {self.emotions['dominant']}")
            if self.emotions.get("tone"):
                emotion_parts.append(f"tone: {self.emotions['tone']}")
            if self.emotions.get("tension_level"):
                emotion_parts.append(f"tension: {self.emotions['tension_level']}")
            if emotion_parts:
                text_parts.append(f"Mood: {', '.join(emotion_parts)}")
                text_parts.append("")
        
        # 6. Interaction Dynamics (New fields)
        dynamics_parts = []
        if self.interaction_pattern:
            dynamics_parts.append(f"Interaction Type: {self.interaction_pattern}")
        if self.initiative:
            dynamics_parts.append(f"Dynamics: {self.initiative}")
        if self.emotional_shift:
            dynamics_parts.append(f"Emotional Shift: {self.emotional_shift}")
        if self.open_loops:
            dynamics_parts.append(f"Open Topics: {', '.join(self.open_loops)}")
        
        if dynamics_parts:
            text_parts.append("Conversation Dynamics:")
            text_parts.extend(dynamics_parts)
            text_parts.append("")

        # 7. Narrative summary (Semantic context)
        if self.narrative_summary:
            text_parts.append(f"Summary: {self.narrative_summary}")

        text_parts.append("")

        # 8. Raw content (Details)
        text_parts.append("Conversation content:")
        text_parts.append(self.content)
        
        return "\n".join(text_parts)



class ConversationChunker:
    """Splits conversations into semantic chunks."""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.timestamp_pattern = re.compile(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.+?):')
    
    def parse_conversation(self, file_path: Path) -> Tuple[Dict, List[Message]]:
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
    
    def format_chunk_content(self, messages: List[Message]) -> str:
        """Formats chunk content for indexing."""
        lines = []
        for msg in messages:
            timestamp = msg.timestamp.strftime('%Y-%m-%d %H:%M')
            content = msg.content if msg.content else ""
            
            if msg.has_media and msg.media_type:
                # Keep media indicators in French to match potential search queries or dataset
                media_indicator = {
                    'photo': '[Photo]',
                    'video': '[Vidéo]',
                    'audio': '[Audio]',
                    'link': ''
                }.get(msg.media_type, '')
                if media_indicator:
                    content = f"{media_indicator} {content}".strip()
            
            if content:
                lines.append(f"[{timestamp}] {msg.author}: {content}")
        
        return '\n'.join(lines)
    
    def chunk_conversation(self, file_path: Path) -> List[Chunk]:
        """Splits a conversation into adaptive chunks."""
        metadata, messages = self.parse_conversation(file_path)

        if not messages:
            return []

        # Skip conversations with deactivated accounts
        conversation_id = metadata['conversation_id']
        if self.config.skip_deactivated_accounts and conversation_id.startswith('utilisateurinstagram_'):
            return []

        # Skip conversations with too few messages
        if len(messages) < self.config.min_messages_per_conversation:
            return []
        
        chunks = []
        chunk_idx = 0
        current_chunk_messages = []
        chunk_start_time = None
        last_msg_time = None
        
        for i, msg in enumerate(messages):
            if not current_chunk_messages:
                chunk_start_time = msg.timestamp
                current_chunk_messages.append(msg)
                last_msg_time = msg.timestamp
                continue
            
            # 1. Calculate deltas
            hours_since_last_msg = (msg.timestamp - last_msg_time).total_seconds() / 3600
            days_elapsed_chunk = (msg.timestamp - chunk_start_time).days
            
            # 2. Splitting criteria
            # A. Time gap (Conversation interrupted > Gap)
            is_time_gap = hours_since_last_msg >= self.config.chunk_time_gap
            
            # B. Size limits (Safety to avoid giant chunks)
            is_too_long = (
                len(current_chunk_messages) >= self.config.chunk_max_messages or
                days_elapsed_chunk >= self.config.chunk_max_days
            )
            
            should_split = is_time_gap or is_too_long
            
            if should_split:
                # Create current chunk
                chunk = self._create_chunk(
                    metadata, current_chunk_messages, chunk_idx, file_path
                )
                chunks.append(chunk)
                chunk_idx += 1
                
                if is_time_gap:
                    # If time gap, start fresh (no overlap needed/relevant)
                    current_chunk_messages = []
                    # But add current message as start of new chunk
                else:
                    # If just too long, use overlap for continuity
                    overlap_start = max(0, len(current_chunk_messages) - self.config.chunk_overlap)
                    current_chunk_messages = current_chunk_messages[overlap_start:]
                
                # Reset for new chunk
                if not current_chunk_messages:
                    chunk_start_time = msg.timestamp
                else:
                    chunk_start_time = current_chunk_messages[0].timestamp
            
            current_chunk_messages.append(msg)
            last_msg_time = msg.timestamp
        
        # Last chunk
        if current_chunk_messages:
            chunk = self._create_chunk(
                metadata, current_chunk_messages, chunk_idx, file_path
            )
            chunks.append(chunk)
        
        return chunks
    
    def _create_chunk(
        self, 
        metadata: Dict, 
        messages: List[Message], 
        chunk_idx: int,
        file_path: Path
    ) -> Chunk:
        """Creates a Chunk object from messages."""
        return Chunk(
            chunk_id=f"{metadata['conversation_id']}_chunk_{chunk_idx:03d}",
            conversation_id=metadata['conversation_id'],
            participants=metadata['participants'],
            date_start=messages[0].timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            date_end=messages[-1].timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            message_count=len(messages),
            content=self.format_chunk_content(messages),
            file_source=file_path.name
        )
    
    def chunk_all_conversations(self, progress_callback=None, limit: int = None) -> List[Chunk]:
        """Splits all conversations in the directory."""
        all_chunks = []
        files = list(self.config.conversations_dir.glob('*.txt'))
        
        if limit:
            files = files[:limit]
            print(f"⚠️  Limit enabled: processing {len(files)} conversations only")

        for i, file_path in enumerate(files):
            try:
                chunks = self.chunk_conversation(file_path)
                all_chunks.extend(chunks)
                
                if progress_callback:
                    progress_callback(i + 1, len(files), file_path.name, len(chunks))
            except Exception as e:
                print(f"⚠️ Error on {file_path.name}: {e}")
                continue
        
        return all_chunks
    
    def save_chunks(self, chunks: List[Chunk], path: Path = None):
        """Saves chunks to JSON."""
        path = path or self.config.chunks_cache_path
        data = [chunk.to_dict() for chunk in chunks]
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_chunks(self, path: Path = None) -> List[Chunk]:
        """Loads chunks from cache."""
        path = path or self.config.chunks_cache_path
        
        if not path.exists():
            return []
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return [Chunk.from_dict(d) for d in data]