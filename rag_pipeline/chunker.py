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
from .chunk_utils import repeat_with_budget


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
    reference_summary: Optional[str] = None  # Ground truth for ROUGE-L validation
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
    
    # Generic metadata for auxiliary info (e.g. complexity scores)
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Chunk":
        # Filter out any unknown fields (e.g., 'summary' from old chunks)
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    def get_compact_content(self) -> str:
        """
        Returns a compact version of content for embeddings and LLM analysis.
        Removes timestamps and shortens names.
        Handles name collisions (Lucie D. / Lucie M.) and special characters.
        """
        # 1. Parse lines first to find all unique authors
        parsed_lines = [] # List of (author|None, content_text)
        authors = set()
        
        for line in self.content.split('\n'):
            # Only process lines that look like messages with our timestamp format
            if line.startswith('[') and '] ' in line:
                try:
                    # [2024-...] Author: Message
                    timestamp_end = line.find('] ')
                    rest = line[timestamp_end + 2:]
                    if ': ' in rest:
                         # Split on first colon only
                        author, msg = rest.split(': ', 1)
                        parsed_lines.append((author, msg))
                        authors.add(author)
                    else:
                        parsed_lines.append((None, line))
                except Exception:
                    parsed_lines.append((None, line))
            else:
                parsed_lines.append((None, line))

        # 2. Build Disambiguated Name Map
        # Step A: Count First Names
        first_name_counts = {}
        for author in authors:
            parts = author.split() if author else []
            first = parts[0] if parts else author
            first_name_counts[first] = first_name_counts.get(first, 0) + 1
            
        # Step B: Generate Initial Candidates
        temp_map = {}
        for author in authors:
            parts = author.split() if author else []
            first = parts[0] if parts else author
            
            if first_name_counts.get(first, 0) <= 1:
                temp_map[author] = first
            else:
                # Collision detected -> Try First + Last Initial
                if len(parts) > 1:
                    # "Lucie Dupont" -> "Lucie D."
                    # Use last part as surname (simple heuristic)
                    last_initial = parts[-1][0]
                    temp_map[author] = f"{first} {last_initial}."
                else:
                    # "Lucie" -> "Lucie" (if unique string, handled above, else keep as is)
                    temp_map[author] = first

        # Step C: Resolve Candidate Collisions (e.g. Lucie D. vs Lucie D.)
        final_map = {}
        # Group by candidate name
        candidate_groups = {}
        for original, candidate in temp_map.items():
            if candidate not in candidate_groups:
                candidate_groups[candidate] = []
            candidate_groups[candidate].append(original)
        
        # Assign final names
        for candidate, original_list in candidate_groups.items():
            if len(original_list) == 1:
                final_map[original_list[0]] = candidate
            else:
                # Still collision? Revert to full name for these specific users
                for original in original_list:
                    final_map[original] = original

        # 3. Reconstruct Content
        output_lines = []
        for author, content in parsed_lines:
            if author:
                short_name = final_map.get(author, author)
                output_lines.append(f"{short_name}: {content}")
            else:
                # Non-message lines (continuations, system messages)
                output_lines.append(content)
        
        return "\n".join(output_lines)

    def get_embedding_text(self) -> str:
        """
        Texte pondéré pour embeddings (dense + BM25 hybride).
        Hiérarchie : voir docs/EMBEDDING_STRATEGY.md
        """

        parts = []

        # 1. Questions hypothétiques — signal dominant, aligne query ↔ document
        #    Budget normalisé pour éviter la domination par volume
        QUESTION_BUDGET = default_config.max_questions
        if self.hypothetical_questions:
            weighted_questions = repeat_with_budget(
                self.hypothetical_questions,
                QUESTION_BUDGET
            )
            for q in weighted_questions:
                parts.append(f"[QUESTION] {q}")

        # 2. Résumé narratif — condensé sémantique dense (1 phrase)
        #    Aide le dense retriever sur les requêtes larges/vagues
        if self.narrative_summary:
            parts.append(f"[SUMMARY] {self.narrative_summary}")

        # 3. Entités — ancres factuelles (x1, BM25 couvre les termes exacts via le contenu brut)
        if self.entities:
            for category, items in self.entities.items():
                if items:
                    for item in items:
                       
                        if item:
                            parts.append(f"[ENTITY:{category}] {item}")

        # 4. Contexte temporel — temps relationnel ("pendant les vacances")
        if self.temporal_context:
            parts.append(f"[TIME] {self.temporal_context}")

        # 5. Intentions — pont entre factuel et social
        if self.speaker_intents:
            for participant, intent in self.speaker_intents.items():
                parts.append(f"[INTENT] {participant}: {intent}")

        # 6. Dynamique structurelle — initiative, boucles ouvertes
        if self.initiative:
            parts.append(f"[INITIATIVE] {self.initiative}")

        if self.open_loops:
            for loop in self.open_loops:
                parts.append(f"[OPEN_LOOP] {loop}")

        # 7. Émotionnel / social — signal faible mais ciblé
        if self.emotions:
            emo = []
            if self.emotions.get("dominant"):
                emo.append(self.emotions["dominant"])
            if self.emotions.get("tone"):
                emo.append(self.emotions["tone"])
            if self.emotions.get("tension_level"):
                emo.append(f"tension:{self.emotions['tension_level']}")
            if emo:
                parts.append(f"[EMOTION] {' | '.join(emo)}")

        if self.interaction_pattern:
            parts.append(f"[INTERACTION] {self.interaction_pattern}")

        if self.emotional_shift:
            parts.append(f"[EMOTIONAL_SHIFT] {self.emotional_shift}")

        # 8. Contenu brut — signal primaire pour BM25 (alpha=0.5), contexte reranker
        parts.append("[CONTENT]")
        parts.append(self.get_compact_content())

        return "\n".join(parts)



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