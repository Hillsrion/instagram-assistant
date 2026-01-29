#!/usr/bin/env python3
"""
Script to merge multiple Instagram exports.

Allows combining multiple Instagram exports (old + new) to preserve
all historical messages, even with the 10k messages limit per export.

Usage:
    python3 merge_instagram_exports.py [export1_dir export2_dir ...] [-o <output_dir>]

    If no export directory is specified, the script will automatically search
    in the 'original_import_folders/' directory.
    Default output is 'merged_instagram_export/'.

Example:
    # Automatic scan and default output
    python3 merge_instagram_exports.py

    # Manual with specific output
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
    """Loads message_1.json from a conversation."""
    message_file = conversation_dir / "message_1.json"

    if not message_file.exists():
        return None

    try:
        with open(message_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠️  Error reading {message_file}: {e}")
        return None


def merge_participants(participants_list: List[List[Dict]]) -> List[Dict]:
    """
    Merges participant lists from multiple exports.
    Deduplicates by 'name'.
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
    Merges multiple message lists by deduplicating via timestamp_ms.

    If two messages have the same timestamp, we keep the one with more content
    (to handle cases where an export might be incomplete).
    """
    messages_by_timestamp: Dict[int, Dict] = {}

    for messages in messages_lists:
        for msg in messages:
            timestamp = msg.get('timestamp_ms')

            if timestamp is None:
                # Message without timestamp, keep it anyway
                # Generate a unique artificial timestamp
                timestamp = -1
                while timestamp in messages_by_timestamp:
                    timestamp -= 1
                messages_by_timestamp[timestamp] = msg
                continue

            # If timestamp already exists, keep the most complete message
            if timestamp in messages_by_timestamp:
                existing = messages_by_timestamp[timestamp]
                existing_content_length = len(json.dumps(existing))
                new_content_length = len(json.dumps(msg))

                # Keep the message with more data
                if new_content_length > existing_content_length:
                    messages_by_timestamp[timestamp] = msg
            else:
                messages_by_timestamp[timestamp] = msg

    # Return sorted by timestamp (chronological)
    return sorted(messages_by_timestamp.values(), key=lambda m: m.get('timestamp_ms', 0))


def merge_conversation(conversation_id: str, export_dirs: List[Path]) -> Dict:
    """
    Merges a specific conversation from multiple exports.

    Args:
        conversation_id: ID of the conversation (folder name)
        export_dirs: List of Instagram export directories

    Returns:
        Merged JSON dictionary of the conversation
    """
    all_data = []

    # Load data from each export
    for export_dir in export_dirs:
        conv_dir = export_dir / conversation_id
        if conv_dir.exists():
            data = load_conversation_json(conv_dir)
            if data:
                all_data.append(data)

    if not all_data:
        return None

    # If only one export has this conversation, return directly
    if len(all_data) == 1:
        return all_data[0]

    # Merge participants
    all_participants = [data.get('participants', []) for data in all_data]
    merged_participants = merge_participants(all_participants)

    # Merge messages
    all_messages = [data.get('messages', []) for data in all_data]
    merged_messages = merge_messages(all_messages)

    # Create merged JSON (take structure of first export as base)
    merged_data = all_data[0].copy()
    merged_data['participants'] = merged_participants
    merged_data['messages'] = merged_messages

    # Add metadata about merge
    if 'title' not in merged_data:
        merged_data['title'] = conversation_id

    return merged_data


def copy_media_files(conversation_id: str, export_dirs: List[Path], output_dir: Path):
    """
    Copies all media files (photos, videos, audio) of a conversation.
    """
    output_conv_dir = output_dir / conversation_id
    output_conv_dir.mkdir(parents=True, exist_ok=True)

    copied_files = set()

    for export_dir in export_dirs:
        conv_dir = export_dir / conversation_id
        if not conv_dir.exists():
            continue

        # Iterate through all items in source folder
        for item in conv_dir.iterdir():
            # If it's a file (except message JSONs already processed)
            if item.is_file():
                if not item.name.startswith("message_") or not item.name.endswith(".json"):
                    dest_path = output_conv_dir / item.name
                    if item.name not in copied_files:
                        try:
                            shutil.copy2(item, dest_path)
                            copied_files.add(item.name)
                        except Exception as e:
                            print(f"    ⚠️  Error copying file {item.name}: {e}")
            
            # If it's a folder (photos, videos, audio, etc.)
            elif item.is_dir():
                dest_dir = output_conv_dir / item.name
                dest_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy folder content recursively
                try:
                    # Use copytree with dirs_exist_ok=True to merge contents
                    # Note: dirs_exist_ok available since Python 3.8
                    shutil.copytree(item, dest_dir, dirs_exist_ok=True)
                except Exception as e:
                    print(f"    ⚠️  Error copying folder {item.name}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Merge multiple Instagram exports to preserve all messages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Automatic scan and default output (merged_instagram_export)
  python3 merge_instagram_exports.py

  # Automatic scan with specific output
  python3 merge_instagram_exports.py -o merged_output

  # Merge two specific exports
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

    # If no folder provided, scan original_import_folders
    export_dirs = []
    if not args.export_dirs:
        base_import_dir = Path("original_import_folders")
        if base_import_dir.exists() and base_import_dir.is_dir():
            print(f"🔍 No folder provided, searching in {base_import_dir}...")
            for item in base_import_dir.iterdir():
                if item.is_dir():
                    # Look for inbox folder in standard structure
                    inbox_path = item / "your_instagram_activity" / "messages" / "inbox"
                    if inbox_path.exists() and inbox_path.is_dir():
                        export_dirs.append(inbox_path)
            
            if not export_dirs:
                print(f"❌ No valid export found in {base_import_dir}")
                return 1
        else:
            print(f"❌ Folder {base_import_dir} not found and no argument provided")
            return 1
    else:
        # Validate manually provided folders
        for export_dir in args.export_dirs:
            if not export_dir.exists():
                print(f"❌ Folder does not exist: {export_dir}")
                return 1
            if not export_dir.is_dir():
                print(f"❌ Not a folder: {export_dir}")
                return 1
            export_dirs.append(export_dir)

    print("=" * 80)
    print("📦 Merge multiple Instagram exports")
    print("=" * 80)
    print()
    print(f"Sources ({len(export_dirs)} exports):")
    for i, export_dir in enumerate(export_dirs, 1):
        print(f"  {i}. {export_dir}")
    print(f"\nDestination: {args.output}")
    print()

    # Collect all unique conversations
    all_conversation_ids: Set[str] = set()
    conversations_by_export: Dict[Path, List[str]] = defaultdict(list)

    for export_dir in export_dirs:
        conv_dirs = [d for d in export_dir.iterdir() if d.is_dir()]
        for conv_dir in conv_dirs:
            conv_id = conv_dir.name
            all_conversation_ids.add(conv_id)
            conversations_by_export[export_dir].append(conv_id)

    print(f"📊 Statistics:")
    print(f"  • Total unique conversations: {len(all_conversation_ids)}")
    for i, export_dir in enumerate(export_dirs, 1):
        count = len(conversations_by_export[export_dir])
        print(f"  • Export {i}: {count} conversations")
    print()

    if args.dry_run:
        print("🔍 Dry-run mode enabled - no merge performed")
        print("\nPreview of conversations to merge:")

        # Analyze a few conversations to show gains
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
            print(f"     → Raw total: {total_messages} messages (before deduplication)")

        if len(all_conversation_ids) > 5:
            print(f"\n  ... and {len(all_conversation_ids) - 5} other conversations")

        return 0

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Merge each conversation
    print("🔄 Merging in progress...\n")

    success_count = 0
    error_count = 0
    total_messages_before = 0
    total_messages_after = 0

    for i, conv_id in enumerate(sorted(all_conversation_ids), 1):
        print(f"[{i}/{len(all_conversation_ids)}] {conv_id}")

        try:
            # Merge JSONs
            merged_data = merge_conversation(conv_id, export_dirs)

            if not merged_data:
                print(f"  ⚠️  No data to merge")
                error_count += 1
                continue

            # Statistics
            messages_before = sum(
                len(load_conversation_json(export_dir / conv_id).get('messages', []))
                for export_dir in export_dirs
                if (export_dir / conv_id).exists() and load_conversation_json(export_dir / conv_id)
            )
            messages_after = len(merged_data.get('messages', []))

            total_messages_before += messages_before
            total_messages_after += messages_after

            duplicates = messages_before - messages_after
            print(f"  ✓ {messages_after} messages ({duplicates} duplicates removed)")

            # Save merged JSON
            output_conv_dir = args.output / conv_id
            output_conv_dir.mkdir(parents=True, exist_ok=True)

            output_file = output_conv_dir / "message_1.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2)

            # Copy media files
            if not args.skip_media:
                copy_media_files(conv_id, export_dirs, args.output)

            success_count += 1

        except Exception as e:
            print(f"  ❌ Error: {e}")
            error_count += 1
            continue

    # Final summary
    print("\n" + "=" * 80)
    print("✅ Merge complete!")
    print("=" * 80)
    print(f"Conversations processed: {success_count}")
    if error_count > 0:
        print(f"Errors: {error_count}")
    print(f"\nMessages:")
    print(f"  • Before merge (raw total): {total_messages_before:,}")
    print(f"  • After merge (deduplicated): {total_messages_after:,}")
    print(f"  • Duplicates removed: {total_messages_before - total_messages_after:,}")
    print(f"\n📁 Result available in: {args.output}")
    print(f"\nNext steps:")
    print(f"  1. Modify instagram_to_text.py line 194 to point to: {args.output}")
    print(f"  2. Run: python3 instagram_to_text.py")
    print(f"  3. Run: python3 update_index.py")

    return 0


if __name__ == "__main__":
    exit(main())