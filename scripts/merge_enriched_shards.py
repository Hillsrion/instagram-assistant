#!/usr/bin/env python3
"""
Merge enriched shard files back into main chunks.json.

After running distributed enrichment with setup_enrich.py on multiple machines,
this script merges the shard files (chunks_shard0.json, chunks_shard1.json, etc.)
back into the main chunks.json file.

Usage:
    python scripts/merge_enriched_shards.py              # Auto-detect and merge all shards
    python scripts/merge_enriched_shards.py --dry-run    # Preview changes without writing
    python scripts/merge_enriched_shards.py --verbose    # Show detailed merge log
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict


def find_shard_files(data_dir: Path) -> List[Path]:
    """Find all chunks_shardN.json files, sorted by index."""
    shard_files = sorted(
        data_dir.glob("chunks_shard*.json"),
        key=lambda p: int(p.stem.split("shard")[1])
    )
    return shard_files


def load_chunks(path: Path) -> Dict[str, dict]:
    """Load chunks from JSON, return as dict keyed by chunk_id."""
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as f:
        chunks_list = json.load(f)

    # Key by chunk_id for easy lookup and update
    return {chunk["chunk_id"]: chunk for chunk in chunks_list}


def merge_shards(chunks_dict: Dict[str, dict], shard_paths: List[Path], verbose: bool = False) -> tuple:
    """
    Merge shard files into chunks_dict.

    Returns: (updated_chunks_dict, merge_stats)
    """
    stats = {
        "total_shards": len(shard_paths),
        "chunks_updated": 0,
        "chunks_new": 0,
        "conflicts": [],
    }

    for shard_path in shard_paths:
        shard_index = int(shard_path.stem.split("shard")[1])
        shard_chunks = load_chunks(shard_path)

        if verbose:
            print(f"  Processing {shard_path.name}: {len(shard_chunks)} chunks")

        for chunk_id, chunk in shard_chunks.items():
            if chunk_id in chunks_dict:
                # Update existing chunk with enrichment fields
                old_chunk = chunks_dict[chunk_id]

                # List of enrichment fields to merge
                enrichment_fields = [
                    "narrative_summary",
                    "hypothetical_questions",
                    "speaker_intents",
                    "temporal_context",
                    "emotions",
                    "entities",
                    "interaction_pattern",
                    "initiative",
                    "emotional_shift",
                    "open_loops"
                ]

                # Check for conflicts (same chunk in multiple shards with different enrichment)
                conflict_detected = False
                for field in enrichment_fields:
                    old_val = old_chunk.get(field)
                    new_val = chunk.get(field)

                    # If both have values and they differ, it's a conflict
                    if (old_val is not None and new_val is not None and
                        str(old_val) != str(new_val) and
                        old_val != "" and new_val != ""):
                        conflict_detected = True
                        break

                if conflict_detected:
                    stats["conflicts"].append({
                        "chunk_id": chunk_id,
                        "shard": shard_index,
                        "issue": "Different enrichment in multiple shards"
                    })
                    if verbose:
                        print(f"    ⚠️  Conflict in {chunk_id}: different enrichment in shard {shard_index}")

                # Update with new enrichment (shard value overwrites if present)
                for field in enrichment_fields:
                    if chunk.get(field):
                        old_chunk[field] = chunk[field]

                stats["chunks_updated"] += 1
            else:
                # New chunk from shard (shouldn't happen in normal operation)
                chunks_dict[chunk_id] = chunk
                stats["chunks_new"] += 1

    return chunks_dict, stats


def validate_merge(original_count: int, merged_count: int, conflicts: List[dict]) -> bool:
    """Validate that merge didn't lose or create unexpected chunks."""
    if merged_count != original_count:
        return False

    if conflicts:
        # Conflicts are warnings, not failures
        return len(conflicts) < 10  # Allow small number of conflicts

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Merge enriched shard files back into chunks.json"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be merged without writing")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed merge progress")
    parser.add_argument("--data-dir", type=Path, default=Path("rag_data"),
                        help="Directory containing chunks.json and shard files")
    args = parser.parse_args()

    data_dir = args.data_dir
    chunks_path = data_dir / "chunks.json"

    # Find shard files
    shard_files = find_shard_files(data_dir)

    if not shard_files:
        print("❌ No shard files found in", data_dir)
        print("   Expected: chunks_shard0.json, chunks_shard1.json, etc.")
        return False

    if not chunks_path.exists():
        print("❌ No chunks.json found in", data_dir)
        print("   Run enrichment on at least one machine first.")
        return False

    print(f"📂 Found {len(shard_files)} shard files:")
    for shard_file in shard_files:
        shard_idx = int(shard_file.stem.split("shard")[1])
        size = shard_file.stat().st_size / (1024 * 1024)
        print(f"   Shard {shard_idx}: {shard_file.name} ({size:.1f} MB)")

    # Load main chunks
    print(f"\n📥 Loading {chunks_path.name}...", end=" ")
    chunks_dict = load_chunks(chunks_path)
    original_count = len(chunks_dict)
    print(f"{original_count} chunks")

    # Merge shards
    print(f"\n🔀 Merging shards...", end="")
    if args.verbose:
        print()
    else:
        print(" ", end="")

    chunks_dict, stats = merge_shards(chunks_dict, shard_files, verbose=args.verbose)

    if not args.verbose:
        print()

    # Validation
    print(f"\n✅ Merge Summary:")
    print(f"   Chunks updated: {stats['chunks_updated']}")
    print(f"   New chunks: {stats['chunks_new']}")
    if stats["conflicts"]:
        print(f"   ⚠️  Conflicts detected: {len(stats['conflicts'])}")
        for conflict in stats["conflicts"][:5]:
            print(f"      - {conflict['chunk_id']} (shard {conflict['shard']}): {conflict['issue']}")
        if len(stats["conflicts"]) > 5:
            print(f"      ... and {len(stats['conflicts']) - 5} more")

    merged_count = len(chunks_dict)
    if not validate_merge(original_count, merged_count, stats["conflicts"]):
        print(f"\n❌ Validation failed: chunk count mismatch ({original_count} -> {merged_count})")
        return False

    print(f"   Total chunks: {original_count} (unchanged ✓)")

    if args.dry_run:
        print(f"\n🔍 Dry-run mode: no changes written")
        return True

    # Create backup
    backup_path = chunks_path.parent / f"chunks.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n💾 Creating backup: {backup_path.name}...", end=" ")
    try:
        with open(chunks_path, "r", encoding="utf-8") as f:
            backup_data = f.read()
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(backup_data)
        print("✓")
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return False

    # Write merged chunks
    print(f"💾 Writing merged chunks to {chunks_path.name}...", end=" ")
    try:
        # Convert dict back to list, preserving order
        chunks_list = list(chunks_dict.values())
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(chunks_list, f, ensure_ascii=False, indent=2)
        print("✓")
    except Exception as e:
        print(f"❌ Failed to write: {e}")
        print(f"   Backup available at: {backup_path}")
        return False

    # Summary
    print(f"\n✨ Merge complete!")
    print(f"   Original chunks: {original_count}")
    print(f"   Final chunks: {merged_count}")
    print(f"   Updated: {stats['chunks_updated']}")
    if stats['chunks_new']:
        print(f"   New: {stats['chunks_new']}")

    print(f"\n📊 Next steps:")
    print(f"   1. Verify: python scripts/check_enrichment_status.py")
    print(f"   2. If all chunks enriched, proceed: python setup_embeddings.py")
    print(f"   3. Optionally, clean up shard files: rm rag_data/chunks_shard*.json")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
