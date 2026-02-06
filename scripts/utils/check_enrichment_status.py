#!/usr/bin/env python3
"""
Script to check enrichment status of all conversations.
Shows which conversations are fully enriched, in progress, or not started.

Usage:
    python3 scripts/check_enrichment_status.py [--detailed]
"""
import argparse
import json
from pathlib import Path
from collections import defaultdict

ENRICHMENT_FIELDS = [
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


def is_chunk_enriched(chunk: dict) -> bool:
    """Returns True if chunk has MAIN enrichment data (summary & questions)."""
    # Strict definition to match setup_enrich.py logic
    return bool(chunk.get("narrative_summary")) and bool(chunk.get("hypothetical_questions"))


def get_enrichment_score(chunk: dict) -> int:
    """Returns number of non-null enrichment fields (0-10)."""
    score = 0
    for field in ENRICHMENT_FIELDS:
        value = chunk.get(field)
        if value is not None and value != "" and value != [] and value != {}:
            score += 1
    return score


def main():
    parser = argparse.ArgumentParser(description="Check enrichment status of conversations")
    parser.add_argument("--detailed", action="store_true", help="Show per-conversation breakdown")
    parser.add_argument("--show-not-enriched", action="store_true", help="List conversations with no enrichment")
    parser.add_argument("--show-in-progress", action="store_true", help="List conversations partially enriched")
    parser.add_argument("--show-enriched", action="store_true", help="List fully enriched and in-progress conversations")
    parser.add_argument("--show-shards", action="store_true", help="Show shard file status during distributed enrichment")
    args = parser.parse_args()

    chunks_path = Path("rag_data/chunks.json")
    data_dir = chunks_path.parent

    # Check for shard files during distributed enrichment
    shard_files = sorted(data_dir.glob("chunks_shard*.json"), key=lambda p: int(p.stem.split("shard")[1]))
    if shard_files and args.show_shards:
        print("🔀 Distributed enrichment in progress (shard files detected):\n")
        for shard_file in shard_files:
            shard_idx = int(shard_file.stem.split("shard")[1])
            with open(shard_file, "r", encoding="utf-8") as f:
                shard_chunks = json.load(f)
            enriched = sum(1 for c in shard_chunks if is_chunk_enriched(c))
            total = len(shard_chunks)
            pct = 100 * enriched / total if total > 0 else 0
            size_mb = shard_file.stat().st_size / (1024 * 1024)
            print(f"  Shard {shard_idx}: {enriched}/{total} enriched ({pct:.1f}%) - {size_mb:.1f} MB")
        print("\n  After all shards complete, run: python scripts/merge_enriched_shards.py\n")

    if not chunks_path.exists():
        print("❌ No chunks.json found in rag_data/")
        return

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    print(f"📂 Loaded {len(chunks)} chunks\n")
    
    # Group by conversation
    by_conversation = defaultdict(list)
    for chunk in chunks:
        conv_id = chunk.get("conversation_id", "unknown")
        by_conversation[conv_id].append(chunk)
    
    # Analyze each conversation
    fully_enriched = []
    in_progress = []
    not_started = []
    
    for conv_id, conv_chunks in by_conversation.items():
        enriched_count = sum(1 for c in conv_chunks if is_chunk_enriched(c))
        total_count = len(conv_chunks)
        
        participants = conv_chunks[0].get("participants", [])[:3]
        participant_str = ", ".join(participants)
        
        conv_info = {
            "id": conv_id,
            "participants": participant_str,
            "total_chunks": total_count,
            "enriched_chunks": enriched_count,
            "percent": 100 * enriched_count / total_count if total_count > 0 else 0
        }
        
        if enriched_count == 0:
            not_started.append(conv_info)
        elif enriched_count == total_count:
            fully_enriched.append(conv_info)
        else:
            in_progress.append(conv_info)
    
    # Summary
    print("=" * 70)
    print("ENRICHMENT STATUS SUMMARY")
    print("=" * 70)
    print(f"  Total conversations: {len(by_conversation)}")
    print(f"  ✅ Fully enriched:   {len(fully_enriched)} ({100*len(fully_enriched)/len(by_conversation):.1f}%)")
    print(f"  🔄 In progress:      {len(in_progress)} ({100*len(in_progress)/len(by_conversation):.1f}%)")
    print(f"  ❌ Not started:      {len(not_started)} ({100*len(not_started)/len(by_conversation):.1f}%)")
    
    # Chunk-level stats
    total_chunks = len(chunks)
    enriched_chunks = sum(1 for c in chunks if is_chunk_enriched(c))
    print(f"\n  Total chunks: {total_chunks}")
    print(f"  Enriched chunks: {enriched_chunks} ({100*enriched_chunks/total_chunks:.1f}%)")
    print(f"  Non-enriched chunks: {total_chunks - enriched_chunks}")
    
    # Show in-progress details
    if args.show_in_progress and in_progress:
        print(f"\n{'=' * 70}")
        print("IN PROGRESS CONVERSATIONS")
        print(f"{'=' * 70}")
        in_progress.sort(key=lambda x: x["percent"], reverse=True)
        for info in in_progress[:20]:
            bar_len = int(info["percent"] / 5)  # 20-char bar
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  {info['id'][:40]:<40} [{bar}] {info['percent']:5.1f}%")
            print(f"    Participants: {info['participants']}")
            print(f"    Chunks: {info['enriched_chunks']}/{info['total_chunks']}")
        if len(in_progress) > 20:
            print(f"  ... and {len(in_progress) - 20} more")
    
    # Show not started
    if args.show_not_enriched and not_started:
        print(f"\n{'=' * 70}")
        print("NOT STARTED CONVERSATIONS")
        print(f"{'=' * 70}")
        not_started.sort(key=lambda x: x["total_chunks"], reverse=True)
        for info in not_started[:20]:
            print(f"  {info['id'][:50]:<50} ({info['total_chunks']} chunks)")
            print(f"    Participants: {info['participants']}")
        if len(not_started) > 20:
            print(f"  ... and {len(not_started) - 20} more")
    
    # Show enriched (fully + in progress)
    if args.show_enriched:
        print(f"\n{'=' * 70}")
        print("FULLY ENRICHED CONVERSATIONS")
        print(f"{'=' * 70}")
        fully_enriched.sort(key=lambda x: x["total_chunks"], reverse=True)
        for info in fully_enriched:
            print(f"  ✅ {info['id']}")
            print(f"     Participants: {info['participants']}")
            print(f"     Chunks: {info['total_chunks']}")
        
        if in_progress:
            print(f"\n{'=' * 70}")
            print("IN PROGRESS CONVERSATIONS")
            print(f"{'=' * 70}")
            in_progress.sort(key=lambda x: x["percent"], reverse=True)
            for info in in_progress:
                print(f"  🔄 {info['id']}")
                print(f"     Participants: {info['participants']}")
                print(f"     Progress: {info['enriched_chunks']}/{info['total_chunks']} ({info['percent']:.1f}%)")
    
    # Detailed per-conversation if requested
    if args.detailed:
        print(f"\n{'=' * 70}")
        print("ALL CONVERSATIONS (sorted by enrichment %)")
        print(f"{'=' * 70}")
        all_convs = fully_enriched + in_progress + not_started
        all_convs.sort(key=lambda x: x["percent"], reverse=True)
        
        for info in all_convs:
            status = "✅" if info["percent"] == 100 else ("🔄" if info["percent"] > 0 else "❌")
            print(f"  {status} {info['id'][:40]:<40} {info['enriched_chunks']:>4}/{info['total_chunks']:<4} ({info['percent']:5.1f}%)")


if __name__ == "__main__":
    main()
