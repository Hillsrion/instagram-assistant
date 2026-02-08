"""
Semantic chunker for Instagram conversations.
Splits conversations into temporal chunks with enriched metadata.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any


from rag_pipeline.core.config import Config, default_config
from rag_pipeline.core.models import Message, Chunk
from rag_pipeline.indexing.parser import InstagramParser


class ConversationChunker:
    """Splits conversations into semantic chunks."""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.parser = InstagramParser()
    
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
        metadata, messages = self.parser.parse_file(file_path)

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
        files = sorted(list(self.config.conversations_dir.glob('*.txt')))
        
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
    
    def save_chunks(self, chunks: List[Chunk], path: Path = None, shard_index: int = None):
        """Saves chunks to JSON.

        Args:
            chunks: List of chunks to save
            path: Optional path override (defaults to config.chunks_cache_path)
            shard_index: If provided, save to chunks_shardN.json instead of chunks.json
        """
        if path is None:
            path = self.config.chunks_cache_path

        # If shard mode, modify filename
        if shard_index is not None:
            path = path.parent / f"chunks_shard{shard_index}.json"

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