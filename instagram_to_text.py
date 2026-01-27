#!/usr/bin/env python3
"""
Convertit les conversations Instagram exportées en documents texte optimisés pour le RAG.
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

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
    
    # Calculer des statistiques enrichies
    media_count = sum(1 for m in messages if 'photos' in m or 'videos' in m or 'audio_files' in m)
    link_count = sum(1 for m in messages if 'share' in m)
    reaction_count = sum(len(m.get('reactions', [])) for m in messages)
    call_count = sum(1 for m in messages if 'call_duration' in m)

    # Créer le document texte
    output_file = output_dir / f"{conv_id}.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        # En-tête enrichi
        f.write(f"# Conversation Instagram avec {conv_name}\n")
        f.write(f"ID: {conv_id}\n")
        f.write(f"Nombre de messages: {len(messages)}\n")

        if messages:
            first_msg_date = format_timestamp(messages[0].get('timestamp_ms', 0))
            last_msg_date = format_timestamp(messages[-1].get('timestamp_ms', 0))
            f.write(f"Période: du {first_msg_date} au {last_msg_date}\n")

        f.write(f"\nParticipants: {', '.join([decode_instagram_text(p.get('name', '')) for p in participants])}\n")

        # Statistiques enrichies
        f.write(f"\nStatistiques:\n")
        f.write(f"  • Médias partagés: {media_count}\n")
        if link_count > 0:
            f.write(f"  • Liens partagés: {link_count}\n")
        if reaction_count > 0:
            f.write(f"  • Réactions totales: {reaction_count}\n")
        if call_count > 0:
            f.write(f"  • Appels: {call_count}\n")

        f.write("\n" + "="*80 + "\n\n")
        
        # Messages
        for msg in messages:
            sender = decode_instagram_text(msg.get('sender_name', 'Inconnu'))
            timestamp = format_timestamp(msg.get('timestamp_ms', 0))
            content = decode_instagram_text(msg.get('content', ''))

            f.write(f"[{timestamp}] {sender}:\n")

            # Contenu du message (ou action spéciale)
            if content:
                # Détecter les actions spéciales Instagram
                if content == "A aimé un message":
                    f.write(f"👍 {content}\n")
                elif content == "A réagi à votre message":
                    f.write(f"👍 {content}\n")
                else:
                    f.write(f"{content}\n")

            # Photos avec URIs si disponibles
            if 'photos' in msg:
                photo_count = len(msg['photos'])
                f.write(f"📷 [{photo_count} photo(s)]")
                # Ajouter les URIs si disponibles (pour contexte)
                photo_uris = [p.get('uri', '') for p in msg['photos'] if p.get('uri')]
                if photo_uris:
                    f.write(f" - Fichiers: {', '.join([Path(uri).name for uri in photo_uris])}")
                f.write("\n")

            # Vidéos avec URIs si disponibles
            if 'videos' in msg:
                video_count = len(msg['videos'])
                f.write(f"🎥 [{video_count} vidéo(s)]")
                video_uris = [v.get('uri', '') for v in msg['videos'] if v.get('uri')]
                if video_uris:
                    f.write(f" - Fichiers: {', '.join([Path(uri).name for uri in video_uris])}")
                f.write("\n")

            # Audio avec URI si disponible
            if 'audio_files' in msg:
                f.write(f"🎵 [Message vocal]")
                if msg['audio_files']:
                    audio_uri = msg['audio_files'][0].get('uri', '')
                    if audio_uri:
                        f.write(f" - Fichier: {Path(audio_uri).name}")
                f.write("\n")

            # Partage de lien avec contexte enrichi
            if 'share' in msg:
                share = msg['share']
                link = share.get('link', '')
                share_text = decode_instagram_text(share.get('share_text', ''))
                original_content_owner = decode_instagram_text(share.get('original_content_owner', ''))

                if link:
                    f.write(f"🔗 Lien partagé: {link}\n")
                # Afficher le texte du share seulement s'il est différent du contenu déjà affiché
                if share_text and share_text.strip() != content.strip():
                    f.write(f"   Texte: {share_text}\n")
                if original_content_owner:
                    f.write(f"   Auteur original: {original_content_owner}\n")

            # Réactions avec emojis exacts
            if 'reactions' in msg:
                reactions = msg['reactions']
                if reactions:
                    reaction_list = []
                    for r in reactions:
                        actor = decode_instagram_text(r.get('actor', ''))
                        reaction = decode_instagram_text(r.get('reaction', ''))
                        if actor and reaction:
                            reaction_list.append(f"{actor} {reaction}")

                    if reaction_list:
                        f.write(f"💬 Réactions: {', '.join(reaction_list)}\n")

            # Stickers/GIFs
            if 'sticker' in msg:
                f.write(f"🎨 [Sticker/GIF partagé]\n")

            # Appels
            if 'call_duration' in msg:
                duration = msg.get('call_duration', 0)
                if duration > 0:
                    minutes = duration // 60
                    seconds = duration % 60
                    f.write(f"📞 [Appel - Durée: {minutes}m {seconds}s]\n")
                else:
                    f.write(f"📞 [Appel manqué]\n")

            # Messages annulés/supprimés (unsent)
            if msg.get('is_unsent', False):
                f.write(f"🗑️ [Message supprimé]\n")

            f.write("\n")
    
    print(f"✓ Converti: {conv_name} ({len(messages)} messages)")

def main():
    """Convertit toutes les conversations Instagram."""
    # Récupérer les chemins depuis les variables d'environnement
    instagram_dir = Path(os.getenv('INSTAGRAM_EXPORT_DIR', '/Users/ismaelsebbane/Documents/your_instagram_activity/messages/inbox'))

    # Base directory du projet
    base_dir = Path(os.getenv('BASE_DIR', Path(__file__).parent))
    conversations_dir = os.getenv('CONVERSATIONS_DIR', 'instagram_conversations')
    output_dir = base_dir / conversations_dir if not Path(conversations_dir).is_absolute() else Path(conversations_dir)

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
