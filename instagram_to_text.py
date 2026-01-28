#!/usr/bin/env python3
"""
Convertit les conversations Instagram exportées en documents texte optimisés pour le RAG.
Se concentre sur une seule source de données (idéalement fusionnée via merge_instagram_exports.py).
"""
import json
import os
import glob
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Optional
from collections import defaultdict
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

def decode_instagram_text(text: str) -> str:
    """Décode le texte Instagram avec encodage spécial."""
    if not text:
        return ""
    # Instagram encode en UTF-8 puis représente les bytes en latin1
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text

def format_timestamp(timestamp_ms: int) -> str:
    """Convertit un timestamp en date lisible."""
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")

def extract_conversation_name(participants: List[Dict]) -> str:
    """Extrait le nom de la conversation."""
    user_name = os.getenv('USER_NAME', 'Ismaël')
    names = [decode_instagram_text(p.get('name', '')) for p in participants]
    # Filtrer le nom de l'utilisateur pour garder le(s) autre(s)
    other_names = [n for n in names if n and user_name not in n]
    if other_names:
        return ' & '.join(other_names)
    return ' & '.join(names)

def get_input_dir() -> Optional[Path]:
    """
    Trouve le meilleur dossier d'entrée (priorité au dossier fusionné).
    """
    project_root = Path(__file__).parent
    
    # 1. Vérifier l'environnement (Priorité absolue si défini)
    env_dir = os.getenv('INSTAGRAM_EXPORT_DIR')
    if env_dir:
        p = Path(env_dir)
        if p.exists():
             # Logique de découverte intelligente
            if p.name == "inbox" and p.is_dir():
                return p
            elif (p / "your_instagram_activity" / "messages" / "inbox").exists():
                return p / "your_instagram_activity" / "messages" / "inbox"
            elif (p / "messages" / "inbox").exists():
                return p / "messages" / "inbox"
            return p

    # 2. Chercher dans merged_instagram_export (Standard recommandé)
    merged_dir = project_root / "merged_instagram_export"
    if merged_dir.exists() and merged_dir.is_dir():
        if (merged_dir / "messages" / "inbox").exists():
            return merged_dir / "messages" / "inbox"

    # 3. Fallback: Chercher dans original_import_folders (Prendre le premier trouvé)
    import_base = project_root / "original_import_folders"
    if import_base.exists() and import_base.is_dir():
        for export_dir in import_base.iterdir():
            if export_dir.is_dir():
                potential_inbox = export_dir / "your_instagram_activity" / "messages" / "inbox"
                if potential_inbox.exists():
                    return potential_inbox
                potential_inbox = export_dir / "messages" / "inbox"
                if potential_inbox.exists():
                    return potential_inbox

    # 4. Fallback: Chercher dans le dossier courant les dossiers instagram-*
    for export_dir in project_root.glob("instagram-*"):
        if export_dir.is_dir():
            potential_inbox = export_dir / "your_instagram_activity" / "messages" / "inbox"
            if potential_inbox.exists():
                return potential_inbox
            potential_inbox = export_dir / "messages" / "inbox"
            if potential_inbox.exists():
                return potential_inbox
    
    return None

def load_conversation_messages(conv_id: str, inbox_dir: Path) -> Dict:
    """
    Charge les messages d'une conversation depuis un dossier unique.
    Gère les fichiers splittés (message_1.json, message_2.json...). 
    """
    conv_path = inbox_dir / conv_id
    if not conv_path.exists():
        return None
        
    all_messages = []
    merged_data = {}
    
    # Trouver tous les message_*.json dans ce dossier
    json_files = sorted(conv_path.glob("message_*.json"))
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Initialiser les métadonnées avec le premier fichier
                if not merged_data or 'participants' not in merged_data:
                    for k, v in data.items():
                        if k != 'messages':
                            merged_data[k] = v
                
                if 'messages' in data:
                    all_messages.extend(data['messages'])
        except Exception as e:
            print(f"  ⚠️  Erreur lecture {json_file.name}: {e}")
                
    if not all_messages:
        return None
        
    # Trier par ordre chronologique
    sorted_messages = sorted(all_messages, key=lambda m: m.get('timestamp_ms', 0))
    merged_data['messages'] = sorted_messages
    
    return merged_data

def convert_to_text(data: Dict, conv_id: str, output_dir: Path) -> None:
    """Génère le fichier texte à partir des données."""
    participants = data.get('participants', [])
    messages = data.get('messages', [])
    
    if not messages:
        return
    
    conv_name = extract_conversation_name(participants)
    
    # Calculer des statistiques
    media_count = sum(1 for m in messages if 'photos' in m or 'videos' in m or 'audio_files' in m)
    link_count = sum(1 for m in messages if 'share' in m)
    reaction_count = sum(len(m.get('reactions', [])) for m in messages)
    call_count = sum(1 for m in messages if 'call_duration' in m)

    output_file = output_dir / f"{conv_id}.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        # En-tête
        f.write(f"# Conversation Instagram avec {conv_name}\n")
        f.write(f"ID: {conv_id}\n")
        f.write(f"Nombre de messages: {len(messages)}\n")

        first_msg_date = format_timestamp(messages[0].get('timestamp_ms', 0))
        last_msg_date = format_timestamp(messages[-1].get('timestamp_ms', 0))
        f.write(f"Période: du {first_msg_date} au {last_msg_date}\n")

        f.write(f"\nParticipants: {', '.join([decode_instagram_text(p.get('name', '')) for p in participants])}\n")

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

            if content:
                if content in ["A aimé un message", "A réagi à votre message"]:
                    f.write(f"👍 {content}\n")
                else:
                    f.write(f"{content}\n")

            # Médias
            if 'photos' in msg:
                f.write(f"📷 [{len(msg['photos'])} photo(s)]\n")
            if 'videos' in msg:
                f.write(f"🎥 [{len(msg['videos'])} vidéo(s)]\n")
            if 'audio_files' in msg:
                f.write(f"🎵 [Message vocal]\n")

            # Partage
            if 'share' in msg:
                share = msg['share']
                link = share.get('link', '')
                if link: f.write(f"🔗 Lien: {link}\n")

            # Réactions
            if 'reactions' in msg:
                reacs = [f"{decode_instagram_text(r.get('actor',''))} {decode_instagram_text(r.get('reaction',''))}" 
                        for r in msg['reactions']]
                f.write(f"💬 Réactions: {', '.join(reacs)}\n")

            if msg.get('is_unsent', False):
                f.write(f"🗑️ [Message supprimé]\n")

            f.write("\n")
    
    print(f"✓ Converti: {conv_name} ({len(messages)} messages)")

def main():
    """Point d'entrée principal."""
    inbox_dir = get_input_dir()
    
    if not inbox_dir:
        print("❌ Aucun dossier d'export Instagram trouvé.")
        print("Veuillez utiliser merge_instagram_exports.py d'abord ou configurer INSTAGRAM_EXPORT_DIR.")
        return

    # Base directory du projet
    base_dir = Path(__file__).parent
    conversations_dir = os.getenv('CONVERSATIONS_DIR', 'rag_data/conversations')
    output_dir = base_dir / conversations_dir
    output_dir.mkdir(exist_ok=True)
    
    print(f"🔄 Conversion des conversations en texte...")
    print(f"📂 Source: {inbox_dir}")
    print(f"📁 Destination: {output_dir}\n")
    
    # Collecter tous les IDs de conversation
    conv_dirs = [d for d in inbox_dir.iterdir() if d.is_dir()]
    sorted_ids = sorted([d.name for d in conv_dirs])
    total = len(sorted_ids)
    
    if total == 0:
        print("⚠️ Aucune conversation trouvée dans ce dossier.")
        return

    for i, conv_id in enumerate(sorted_ids, 1):
        print(f"[{i}/{total}] {conv_id}... ", end='', flush=True)
        data = load_conversation_messages(conv_id, inbox_dir)
        if data:
            convert_to_text(data, conv_id, output_dir)
        else:
            print("⚠️ Vide ou illisible")
    
    print(f"\n✅ Terminé ! {total} conversations traitées.")

if __name__ == "__main__":
    main()
