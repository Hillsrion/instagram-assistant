#!/usr/bin/env python3
"""
Convertit les conversations Instagram exportées en documents texte optimisés pour le RAG.
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List

def decode_instagram_text(text: str) -> str:
    """Décode le texte Instagram avec encodage spécial."""
    if not text:
        return ""
    # Instagram encode en UTF-8 puis représente les bytes
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text

def format_timestamp(timestamp_ms: int) -> str:
    """Convertit un timestamp en date lisible."""
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")

def extract_conversation_name(participants: List[Dict]) -> str:
    """Extrait le nom de la conversation."""
    names = [decode_instagram_text(p.get('name', '')) for p in participants]
    # Filtrer le nom de l'utilisateur (Ismaël) pour garder le(s) autre(s)
    other_names = [n for n in names if n and n != 'Ismaël']
    if other_names:
        return ' & '.join(other_names)
    return ' & '.join(names)

def convert_conversation(conversation_path: Path, output_dir: Path) -> None:
    """Convertit une conversation Instagram en fichier texte."""
    message_file = conversation_path / "message_1.json"
    
    if not message_file.exists():
        return
    
    try:
        with open(message_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Erreur lecture {message_file}: {e}")
        return
    
    participants = data.get('participants', [])
    messages = data.get('messages', [])
    
    if not messages:
        return
    
    # Nom de la conversation
    conv_name = extract_conversation_name(participants)
    conv_id = conversation_path.name
    
    # Trier les messages par ordre chronologique (du plus ancien au plus récent)
    messages.sort(key=lambda m: m.get('timestamp_ms', 0))
    
    # Créer le document texte
    output_file = output_dir / f"{conv_id}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # En-tête
        f.write(f"# Conversation Instagram avec {conv_name}\n")
        f.write(f"ID: {conv_id}\n")
        f.write(f"Nombre de messages: {len(messages)}\n")
        
        if messages:
            first_msg_date = format_timestamp(messages[0].get('timestamp_ms', 0))
            last_msg_date = format_timestamp(messages[-1].get('timestamp_ms', 0))
            f.write(f"Période: du {first_msg_date} au {last_msg_date}\n")
        
        f.write(f"\nParticipants: {', '.join([decode_instagram_text(p.get('name', '')) for p in participants])}\n")
        f.write("\n" + "="*80 + "\n\n")
        
        # Messages
        for msg in messages:
            sender = decode_instagram_text(msg.get('sender_name', 'Inconnu'))
            timestamp = format_timestamp(msg.get('timestamp_ms', 0))
            content = decode_instagram_text(msg.get('content', ''))
            
            f.write(f"[{timestamp}] {sender}:\n")
            
            if content:
                f.write(f"{content}\n")
            
            # Photos
            if 'photos' in msg:
                photo_count = len(msg['photos'])
                f.write(f"📷 [{photo_count} photo(s)]\n")
            
            # Vidéos
            if 'videos' in msg:
                video_count = len(msg['videos'])
                f.write(f"🎥 [{video_count} vidéo(s)]\n")
            
            # Audio
            if 'audio_files' in msg:
                f.write(f"🎵 [Message vocal]\n")
            
            # Partage de lien
            if 'share' in msg:
                link = msg['share'].get('link', '')
                if link:
                    f.write(f"🔗 {link}\n")
            
            # Réactions
            if 'reactions' in msg:
                reactions = msg['reactions']
                reaction_text = ', '.join([
                    f"{decode_instagram_text(r.get('actor', ''))} {decode_instagram_text(r.get('reaction', ''))}"
                    for r in reactions
                ])
                f.write(f"❤️ Réactions: {reaction_text}\n")
            
            f.write("\n")
    
    print(f"✓ Converti: {conv_name} ({len(messages)} messages)")

def main():
    """Convertit toutes les conversations Instagram."""
    instagram_dir = Path("/Users/ismaelsebbane/Documents/your_instagram_activity/messages/inbox")
    output_dir = Path("/Users/ismaelsebbane/dev/lab/instagram-assistant/instagram_conversations")
    
    # Créer le dossier de sortie
    output_dir.mkdir(exist_ok=True)
    
    print(f"🔄 Conversion des conversations Instagram...")
    print(f"📂 Source: {instagram_dir}")
    print(f"📁 Destination: {output_dir}\n")
    
    # Parcourir toutes les conversations
    conversation_dirs = [d for d in instagram_dir.iterdir() if d.is_dir()]
    
    for i, conv_dir in enumerate(conversation_dirs, 1):
        print(f"[{i}/{len(conversation_dirs)}] ", end='')
        convert_conversation(conv_dir, output_dir)
    
    print(f"\n✅ Conversion terminée ! {len(conversation_dirs)} conversations traitées.")
    print(f"📁 Fichiers disponibles dans: {output_dir}")

if __name__ == "__main__":
    main()
