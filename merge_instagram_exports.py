#!/usr/bin/env python3
"""
Script de merge d'exports Instagram multiples.

Permet de combiner plusieurs exports Instagram (ancien + nouveau) pour conserver
tous les messages historiques, même avec la limite des 10k messages par export.

Usage:
    python3 merge_instagram_exports.py [export1_dir export2_dir ...] [-o <output_dir>]

    Si aucun dossier d'export n'est spécifié, le script cherchera automatiquement
    dans le dossier 'original_import_folders/'.
    La sortie par défaut est 'merged_instagram_export/'.

Exemple:
    # Scan automatique et sortie par défaut
    python3 merge_instagram_exports.py

    # Manuel avec sortie spécifique
    python3 merge_instagram_exports.py \
        ~/Documents/export_2024_06/messages/inbox \
        -o ~/Documents/merged_inbox
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set
from collections import defaultdict
import argparse


def load_conversation_json(conversation_dir: Path) -> Dict:
    """Charge le message_1.json d'une conversation."""
    message_file = conversation_dir / "message_1.json"

    if not message_file.exists():
        return None

    try:
        with open(message_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠️  Erreur lecture {message_file}: {e}")
        return None


def merge_participants(participants_list: List[List[Dict]]) -> List[Dict]:
    """
    Merge les listes de participants de plusieurs exports.
    Déduplique par 'name'.
    """
    seen_names = set()
    merged = []

    for participants in participants_list:
        for participant in participants:
            name = participant.get('name', '')
            if name and name not in seen_names:
                seen_names.add(name)
                merged.append(participant)

    return merged


def merge_messages(messages_lists: List[List[Dict]]) -> List[Dict]:
    """
    Merge plusieurs listes de messages en déduplicant par timestamp_ms.

    Si deux messages ont le même timestamp, on garde celui avec le plus de contenu
    (pour gérer les cas où un export serait incomplet).
    """
    messages_by_timestamp: Dict[int, Dict] = {}

    for messages in messages_lists:
        for msg in messages:
            timestamp = msg.get('timestamp_ms')

            if timestamp is None:
                # Message sans timestamp, on le garde quand même
                # On génère un timestamp unique artificiel
                timestamp = -1
                while timestamp in messages_by_timestamp:
                    timestamp -= 1
                messages_by_timestamp[timestamp] = msg
                continue

            # Si le timestamp existe déjà, on garde le message le plus complet
            if timestamp in messages_by_timestamp:
                existing = messages_by_timestamp[timestamp]
                existing_content_length = len(json.dumps(existing))
                new_content_length = len(json.dumps(msg))

                # Garder le message avec le plus de données
                if new_content_length > existing_content_length:
                    messages_by_timestamp[timestamp] = msg
            else:
                messages_by_timestamp[timestamp] = msg

    # Retourner triés par timestamp (chronologique)
    return sorted(messages_by_timestamp.values(), key=lambda m: m.get('timestamp_ms', 0))


def merge_conversation(conversation_id: str, export_dirs: List[Path]) -> Dict:
    """
    Merge une conversation spécifique depuis plusieurs exports.

    Args:
        conversation_id: ID de la conversation (nom du dossier)
        export_dirs: Liste des dossiers d'export Instagram

    Returns:
        Dictionnaire JSON mergé de la conversation
    """
    all_data = []

    # Charger les données de chaque export
    for export_dir in export_dirs:
        conv_dir = export_dir / conversation_id
        if conv_dir.exists():
            data = load_conversation_json(conv_dir)
            if data:
                all_data.append(data)

    if not all_data:
        return None

    # Si un seul export a cette conversation, retourner directement
    if len(all_data) == 1:
        return all_data[0]

    # Merger les participants
    all_participants = [data.get('participants', []) for data in all_data]
    merged_participants = merge_participants(all_participants)

    # Merger les messages
    all_messages = [data.get('messages', []) for data in all_data]
    merged_messages = merge_messages(all_messages)

    # Créer le JSON mergé (prendre la structure du premier export comme base)
    merged_data = all_data[0].copy()
    merged_data['participants'] = merged_participants
    merged_data['messages'] = merged_messages

    # Ajouter des métadonnées sur le merge
    if 'title' not in merged_data:
        merged_data['title'] = conversation_id

    return merged_data


def copy_media_files(conversation_id: str, export_dirs: List[Path], output_dir: Path):
    """
    Copie tous les fichiers média (photos, vidéos, audio) d'une conversation.
    """
    output_conv_dir = output_dir / conversation_id
    output_conv_dir.mkdir(parents=True, exist_ok=True)

    copied_files = set()

    for export_dir in export_dirs:
        conv_dir = export_dir / conversation_id
        if not conv_dir.exists():
            continue

        # Parcourir tous les éléments du dossier source
        for item in conv_dir.iterdir():
            # Si c'est un fichier (sauf les JSON de messages déjà traités)
            if item.is_file():
                if not item.name.startswith("message_") or not item.name.endswith(".json"):
                    dest_path = output_conv_dir / item.name
                    if item.name not in copied_files:
                        try:
                            shutil.copy2(item, dest_path)
                            copied_files.add(item.name)
                        except Exception as e:
                            print(f"    ⚠️  Erreur copie fichier {item.name}: {e}")
            
            # Si c'est un dossier (photos, videos, audio, etc.)
            elif item.is_dir():
                dest_dir = output_conv_dir / item.name
                dest_dir.mkdir(parents=True, exist_ok=True)
                
                # Copier le contenu du dossier récursivement
                try:
                    # On utilise copytree avec dirs_exist_ok=True pour merger les contenus
                    # Note: dirs_exist_ok est dispo depuis Python 3.8
                    shutil.copytree(item, dest_dir, dirs_exist_ok=True)
                except Exception as e:
                    print(f"    ⚠️  Erreur copie dossier {item.name}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Merge multiple Instagram exports to preserve all messages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan automatique et sortie par défaut (merged_instagram_export)
  python3 merge_instagram_exports.py

  # Scan automatique avec sortie spécifique
  python3 merge_instagram_exports.py -o merged_output

  # Merge deux exports spécifiques
  python3 merge_instagram_exports.py \
      ~/Documents/export1/messages/inbox \
      ~/Documents/export2/messages/inbox \
      -o ~/Documents/merged/messages/inbox
        """
    )

    parser.add_argument(
        'export_dirs',
        nargs='*',
        type=Path,
        help='Directories containing Instagram exports (inbox folders). If empty, scans original_import_folders/'
    )

    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path('merged_instagram_export'),
        help='Output directory for merged conversations (default: merged_instagram_export)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show statistics without merging'
    )

    parser.add_argument(
        '--skip-media',
        action='store_true',
        help='Skip copying media files (only merge JSON)'
    )

    args = parser.parse_args()

    # Si aucun dossier fourni, scanner original_import_folders
    export_dirs = []
    if not args.export_dirs:
        base_import_dir = Path("original_import_folders")
        if base_import_dir.exists() and base_import_dir.is_dir():
            print(f"🔍 Aucun dossier fourni, recherche dans {base_import_dir}...")
            for item in base_import_dir.iterdir():
                if item.is_dir():
                    # Chercher le dossier inbox dans la structure standard
                    inbox_path = item / "your_instagram_activity" / "messages" / "inbox"
                    if inbox_path.exists() and inbox_path.is_dir():
                        export_dirs.append(inbox_path)
            
            if not export_dirs:
                print(f"❌ Aucune exportation valide trouvée dans {base_import_dir}")
                return 1
        else:
            print(f"❌ Dossier {base_import_dir} introuvable et aucun argument fourni")
            return 1
    else:
        # Valider les dossiers fournis manuellement
        for export_dir in args.export_dirs:
            if not export_dir.exists():
                print(f"❌ Dossier inexistant: {export_dir}")
                return 1
            if not export_dir.is_dir():
                print(f"❌ Pas un dossier: {export_dir}")
                return 1
            export_dirs.append(export_dir)

    print("=" * 80)
    print("📦 Merge d'exports Instagram multiples")
    print("=" * 80)
    print()
    print(f"Sources ({len(export_dirs)} exports):")
    for i, export_dir in enumerate(export_dirs, 1):
        print(f"  {i}. {export_dir}")
    print(f"\nDestination: {args.output}")
    print()

    # Collecter toutes les conversations uniques
    all_conversation_ids: Set[str] = set()
    conversations_by_export: Dict[Path, List[str]] = defaultdict(list)

    for export_dir in export_dirs:
        conv_dirs = [d for d in export_dir.iterdir() if d.is_dir()]
        for conv_dir in conv_dirs:
            conv_id = conv_dir.name
            all_conversation_ids.add(conv_id)
            conversations_by_export[export_dir].append(conv_id)

    print(f"📊 Statistiques:")
    print(f"  • Total de conversations uniques: {len(all_conversation_ids)}")
    for i, export_dir in enumerate(export_dirs, 1):
        count = len(conversations_by_export[export_dir])
        print(f"  • Export {i}: {count} conversations")
    print()

    if args.dry_run:
        print("🔍 Mode dry-run activé - pas de merge effectué")
        print("\nAperçu des conversations à merger:")

        # Analyser quelques conversations pour montrer les gains
        sample_conversations = list(all_conversation_ids)[:5]
        for conv_id in sample_conversations:
            print(f"\n  📁 {conv_id}")
            total_messages = 0
            for export_dir in export_dirs:
                conv_dir = export_dir / conv_id
                if conv_dir.exists():
                    data = load_conversation_json(conv_dir)
                    if data:
                        msg_count = len(data.get('messages', []))
                        total_messages += msg_count
                        print(f"     Export: {msg_count} messages")
            print(f"     → Total brut: {total_messages} messages (avant déduplications)")

        if len(all_conversation_ids) > 5:
            print(f"\n  ... et {len(all_conversation_ids) - 5} autres conversations")

        return 0

    # Créer le dossier de sortie
    args.output.mkdir(parents=True, exist_ok=True)

    # Merger chaque conversation
    print("🔄 Merge en cours...\n")

    success_count = 0
    error_count = 0
    total_messages_before = 0
    total_messages_after = 0

    for i, conv_id in enumerate(sorted(all_conversation_ids), 1):
        print(f"[{i}/{len(all_conversation_ids)}] {conv_id}")

        try:
            # Merger les JSON
            merged_data = merge_conversation(conv_id, export_dirs)

            if not merged_data:
                print(f"  ⚠️  Aucune donnée à merger")
                error_count += 1
                continue

            # Statistiques
            messages_before = sum(
                len(load_conversation_json(export_dir / conv_id).get('messages', []))
                for export_dir in export_dirs
                if (export_dir / conv_id).exists() and load_conversation_json(export_dir / conv_id)
            )
            messages_after = len(merged_data.get('messages', []))

            total_messages_before += messages_before
            total_messages_after += messages_after

            duplicates = messages_before - messages_after
            print(f"  ✓ {messages_after} messages ({duplicates} doublons supprimés)")

            # Sauvegarder le JSON mergé
            output_conv_dir = args.output / conv_id
            output_conv_dir.mkdir(parents=True, exist_ok=True)

            output_file = output_conv_dir / "message_1.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2)

            # Copier les fichiers média
            if not args.skip_media:
                copy_media_files(conv_id, export_dirs, args.output)

            success_count += 1

        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            error_count += 1
            continue

    # Résumé final
    print("\n" + "=" * 80)
    print("✅ Merge terminé !")
    print("=" * 80)
    print(f"Conversations traitées: {success_count}")
    if error_count > 0:
        print(f"Erreurs: {error_count}")
    print(f"\nMessages:")
    print(f"  • Avant merge (total brut): {total_messages_before:,}")
    print(f"  • Après merge (dédupliqués): {total_messages_after:,}")
    print(f"  • Doublons supprimés: {total_messages_before - total_messages_after:,}")
    print(f"\n📁 Résultat disponible dans: {args.output}")
    print(f"\nProchaine étape:")
    print(f"  1. Modifiez instagram_to_text.py ligne 194 pour pointer vers: {args.output}")
    print(f"  2. Lancez: python3 instagram_to_text.py")
    print(f"  3. Lancez: python3 update_index.py")

    return 0


if __name__ == "__main__":
    exit(main())
