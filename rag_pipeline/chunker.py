"""
Chunker sémantique pour conversations Instagram.
Découpe les conversations en chunks temporels avec métadonnées enrichies.
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
    """Un message individuel."""
    timestamp: datetime
    author: str
    content: str
    has_media: bool = False
    media_type: Optional[str] = None  # photo, video, audio, link


@dataclass
class Chunk:
    """Un chunk de conversation avec métadonnées enrichies."""
    chunk_id: str
    conversation_id: str
    participants: List[str]
    date_start: str
    date_end: str
    message_count: int
    summary: str
    content: str
    file_source: str
    # Nouveaux champs pour le RAG "Gold Standard"
    narrative_summary: Optional[str] = None
    hypothetical_questions: Optional[List[str]] = None
    speaker_intents: Optional[Dict[str, str]] = None
    temporal_context: Optional[str] = None
    emotions: Optional[Dict[str, Any]] = None  # {dominant, tone, tension_level}
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Chunk":
        return cls(**data)
    
    def get_embedding_text(self) -> str:
        """
        Retourne le texte à encoder (Questions + Résumé + Contenu).
        L'inclusion des questions hypothétiques améliore drastiquement le retrieval.
        """
        text_parts = []
        
        # 1. Questions hypothétiques (Priorité haute pour le matching)
        if self.hypothetical_questions:
            text_parts.append("Questions auxquelles ce document répond :")
            text_parts.extend(self.hypothetical_questions)
            text_parts.append("")

        # 2. Contexte temporel sémantique
        if self.temporal_context:
            text_parts.append(f"Période : {self.temporal_context}")
            text_parts.append("")

        # 3. Intentions des participants
        if self.speaker_intents:
            text_parts.append("Intentions des participants :")
            for participant, intent in self.speaker_intents.items():
                text_parts.append(f"  - {participant} : {intent}")
            text_parts.append("")

        # 4. Émotions (Contexte émotionnel)
        if self.emotions:
            emotion_parts = []
            if self.emotions.get("dominant"):
                emotion_parts.append(f"émotion dominante: {self.emotions['dominant']}")
            if self.emotions.get("tone"):
                emotion_parts.append(f"ton: {self.emotions['tone']}")
            if self.emotions.get("tension_level"):
                emotion_parts.append(f"tension: {self.emotions['tension_level']}")
            if emotion_parts:
                text_parts.append(f"Ambiance : {', '.join(emotion_parts)}")
                text_parts.append("")

        # 5. Résumé narratif (Contexte sémantique)
        if self.narrative_summary:
            text_parts.append(f"Résumé : {self.narrative_summary}")
        else:
            text_parts.append(f"Résumé statistique : {self.summary}")

        text_parts.append("")

        # 6. Contenu brut (Détails)
        text_parts.append("Contenu de la conversation :")
        text_parts.append(self.content)
        
        return "\n".join(text_parts)



class ConversationChunker:
    """Découpe les conversations en chunks sémantiques."""
    
    def __init__(self, config: Config = None):
        self.config = config or default_config
        self.timestamp_pattern = re.compile(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.+?):')
    
    def parse_conversation(self, file_path: Path) -> Tuple[Dict, List[Message]]:
        """Parse un fichier de conversation et extrait les métadonnées et messages."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        # Extraire les métadonnées de l'en-tête
        metadata = {
            'conversation_id': file_path.stem,
            'file_source': file_path.name,
            'participants': [],
            'title': '',
        }
        
        header_end = 0
        for i, line in enumerate(lines):
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
        
        # Parser les messages
        messages = []
        current_message = None
        current_content_lines = []
        
        for line in lines[header_end:]:
            match = self.timestamp_pattern.match(line)
            
            if match:
                # Sauvegarder le message précédent
                if current_message is not None:
                    current_message.content = '\n'.join(current_content_lines).strip()
                    if current_message.content or current_message.has_media:
                        messages.append(current_message)
                
                # Nouveau message
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
                # Contenu du message
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
        
        # Dernier message
        if current_message is not None:
            current_message.content = '\n'.join(current_content_lines).strip()
            if current_message.content or current_message.has_media:
                messages.append(current_message)
        
        return metadata, messages
    
    def generate_summary(self, messages: List[Message], participants: List[str]) -> str:
        """Génère un résumé court du chunk."""
        if not messages:
            return "Chunk vide"
        
        # Participants actifs dans ce chunk
        active_authors = set(m.author for m in messages)
        other_participants = [p for p in active_authors if p != self.config.user_name]
        
        # Période
        start = messages[0].timestamp.strftime('%d/%m/%Y')
        end = messages[-1].timestamp.strftime('%d/%m/%Y')
        period = f"{start}" if start == end else f"{start} - {end}"
        
        # Comptage par auteur
        author_counts = defaultdict(int)
        for m in messages:
            author_counts[m.author] += 1
        
        # Mots-clés simples (les mots les plus fréquents > 4 caractères)
        all_words = []
        for m in messages:
            words = re.findall(r'\b[a-zA-ZÀ-ÿ]{5,}\b', m.content.lower())
            all_words.extend(words)
        
        word_freq = defaultdict(int)
        stopwords = {'avoir', 'être', 'faire', 'cette', 'aussi', 'comme', 'encore', 
                     'toujours', 'jamais', 'alors', 'quand', 'après', 'avant', 'depuis',
                     'comment', 'pourquoi', 'parce', 'vraiment', 'tellement', 'quelque'}
        for w in all_words:
            if w not in stopwords:
                word_freq[w] += 1
        
        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        keywords = [w for w, _ in top_words] if top_words else []
        
        # Construire le résumé
        summary_parts = [
            f"Conversation entre {self.config.user_name} et {', '.join(other_participants) if other_participants else 'participants'}.",
            f"Période: {period}.",
            f"{len(messages)} messages échangés.",
        ]
        
        if keywords:
            summary_parts.append(f"Sujets abordés: {', '.join(keywords)}.")
        
        # Média
        media_count = sum(1 for m in messages if m.has_media)
        if media_count > 0:
            summary_parts.append(f"Contient {media_count} média(s).")
        
        return " ".join(summary_parts)
    
    def format_chunk_content(self, messages: List[Message]) -> str:
        """Formate le contenu d'un chunk pour l'indexation."""
        lines = []
        for msg in messages:
            timestamp = msg.timestamp.strftime('%Y-%m-%d %H:%M')
            content = msg.content if msg.content else ""
            
            if msg.has_media and msg.media_type:
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
        """Découpe une conversation en chunks."""
        metadata, messages = self.parse_conversation(file_path)
        
        if not messages:
            return []
        
        chunks = []
        chunk_idx = 0
        current_chunk_messages = []
        chunk_start_time = None
        
        for msg in messages:
            if not current_chunk_messages:
                chunk_start_time = msg.timestamp
                current_chunk_messages.append(msg)
                continue
            
            # Calculer la durée depuis le début du chunk
            days_elapsed = (msg.timestamp - chunk_start_time).days
            
            # Conditions de création d'un nouveau chunk
            should_split = (
                len(current_chunk_messages) >= self.config.chunk_max_messages or
                days_elapsed >= self.config.chunk_max_days
            )
            
            if should_split:
                # Créer le chunk actuel
                chunk = self._create_chunk(
                    metadata, current_chunk_messages, chunk_idx, file_path
                )
                chunks.append(chunk)
                chunk_idx += 1
                
                # Commencer un nouveau chunk avec overlap
                overlap_start = max(0, len(current_chunk_messages) - self.config.chunk_overlap)
                current_chunk_messages = current_chunk_messages[overlap_start:]
                chunk_start_time = current_chunk_messages[0].timestamp if current_chunk_messages else msg.timestamp
            
            current_chunk_messages.append(msg)
        
        # Dernier chunk
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
        """Crée un objet Chunk à partir des messages."""
        return Chunk(
            chunk_id=f"{metadata['conversation_id']}_chunk_{chunk_idx:03d}",
            conversation_id=metadata['conversation_id'],
            participants=metadata['participants'],
            date_start=messages[0].timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            date_end=messages[-1].timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            message_count=len(messages),
            summary=self.generate_summary(messages, metadata['participants']),
            content=self.format_chunk_content(messages),
            file_source=file_path.name
        )
    
    def chunk_all_conversations(self, progress_callback=None, limit: int = None) -> List[Chunk]:
        """Découpe toutes les conversations du dossier."""
        all_chunks = []
        files = list(self.config.conversations_dir.glob('*.txt'))
        
        if limit:
            files = files[:limit]
            print(f"⚠️  Limite activée: traitement de {len(files)} conversations seulement")

        for i, file_path in enumerate(files):
            try:
                chunks = self.chunk_conversation(file_path)
                all_chunks.extend(chunks)
                
                if progress_callback:
                    progress_callback(i + 1, len(files), file_path.name, len(chunks))
            except Exception as e:
                print(f"⚠️ Erreur sur {file_path.name}: {e}")
                continue
        
        return all_chunks
    
    def save_chunks(self, chunks: List[Chunk], path: Path = None):
        """Sauvegarde les chunks en JSON."""
        path = path or self.config.chunks_cache_path
        data = [chunk.to_dict() for chunk in chunks]
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_chunks(self, path: Path = None) -> List[Chunk]:
        """Charge les chunks depuis le cache."""
        path = path or self.config.chunks_cache_path
        
        if not path.exists():
            return []
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return [Chunk.from_dict(d) for d in data]
