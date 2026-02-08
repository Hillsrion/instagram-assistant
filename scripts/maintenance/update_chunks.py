#!/usr/bin/env python3
"""
Script to update chunks while preserving existing enrichments.
Use this when you have added new messages to your conversation files
or added new conversation files entirely.

Mechanics:
1. Loads existing chunks.json (to keep enrichments).
2. Re-processes all .txt files to generate fresh chunks.
3. Matches fresh chunks with existing ones based on CONTENT HASH.
   - Match found: Keep existing chunk (preserves summary, questions, etc.)
   - No match: Use fresh chunk (will need enrichment)
4. Saves the updated list to chunks.json.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))
import json
import hashlib
import argparse
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.core.config import Config
from rag_pipeline.indexing.chunker import ConversationChunker
from rag_pipeline.core.models import Chunk
from rag_pipeline.utils.cli_utils import print_header

def get_content_hash(text: str) -> str:
    """Returns MD5 hash of the text (normalized)."""
    # Normalize line endings just in case
    normalized_text = text.replace('\r\n', '\n').strip()
    return hashlib.md5(normalized_text.encode('utf-8')).hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Update chunks from files while preserving enrichment")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without saving")
    args = parser.parse_args()

    config = Config()
    chunker = ConversationChunker(config)
    chunks_path = config.chunks_cache_path

    print_header("Updating Chunks (Incremental)", step="Maintenance")

    # 1. Load Existing Data
    existing_chunks_map: Dict[str, Chunk] = {}
    if chunks_path.exists():
        print(f"📂 Loading existing database from {chunks_path}...")
        existing_list = chunker.load_chunks()
        
        # We index by CONTENT HASH because IDs might shift if we insert messages in the past 
        # (though usually chunks are append-only, hash is safer)
        for c in existing_list:
            h = get_content_hash(c.content)
            # Store the first occurrence (duplicates shouldn't exist theoretically)
            if h not in existing_chunks_map:
                existing_chunks_map[h] = c
        
        print(f"   Loaded {len(existing_list)} existing chunks.")
        
        # Count enriched
        enriched_count = sum(1 for c in existing_list if c.narrative_summary)
        print(f"   Enriched chunks preserved in memory: {enriched_count}")
    else:
        print("⚠️  No existing chunks.json found. This will be a fresh generation.")

    # 2. Generate Fresh Chunks from Files
    print("\n🔄 Re-scanning source files...")
    
    # Using the standardized sorted order from our previous fix
    fresh_chunks = chunker.chunk_all_conversations(
        progress_callback=lambda c, t, f, n: print(f"   Processing {f}..." if c % 100 == 0 else "", end="\r")
    )
    print(f"\n   Scanned {len(fresh_chunks)} chunks from current files.")

    # 3. Merge Strategy
    merged_chunks = []
    stats = {
        "preserved": 0,
        "new_or_modified": 0,
        "chunks_with_enrichment_kept": 0
    }

    for fresh_chunk in fresh_chunks:
        h = get_content_hash(fresh_chunk.content)
        
        if h in existing_chunks_map:
            # PERFECT MATCH: The content is identical to what we had.
            # We preserve the OLD object because it contains the enrichment (summaries, etc.)
            existing_chunk = existing_chunks_map[h]
            
            # We still update metadata that might be dynamic but not semantic content
            # (e.g., file_source if renamed, though content check handles that)
            # But critically, we keep the ID from the NEW generation to ensure consistent numbering 
            # if we want to rely on the new file order.
            
            # Wait, if we use the old object, we keep the OLD ID. 
            # If the file order changed, the OLD ID might be wrong (e.g. chunk_050 became chunk_051).
            # STRATEGY: Take fresh chunk (correct ID/Metadata) and copy enrichment from old chunk.
            
            # Fields to copy from the "Golden" existing chunk
            enrichment_fields = [
                "narrative_summary", "reference_summary", "hypothetical_questions", 
                "speaker_intents", "temporal_context", "emotions", "entities",
                "interaction_pattern", "initiative", "emotional_shift", "open_loops"
            ]
            
            has_enrichment = False
            for field in enrichment_fields:
                val = getattr(existing_chunk, field, None)
                if val:
                    setattr(fresh_chunk, field, val)
                    has_enrichment = True
            
            merged_chunks.append(fresh_chunk)
            stats["preserved"] += 1
            if has_enrichment:
                stats["chunks_with_enrichment_kept"] += 1
                
        else:
            # NO MATCH: This is new content (or modified content).
            # We keep the fresh chunk as is (unenriched).
            merged_chunks.append(fresh_chunk)
            stats["new_or_modified"] += 1

    # 4. Report & Save
    print("\n" + "="*40)
    print("MERGE REPORT")
    print("="*40)
    print(f"Total chunks in new set:      {len(merged_chunks)}")
    print(f"✅ Unchanged (Enrichment kept): {stats['chunks_with_enrichment_kept']}")
    print(f"🆕 New or Modified (To enrich): {stats['new_or_modified']}")
    print("="*40)

    if args.dry_run:
        print("\n🚫 Dry-run: File NOT updated.")
    else:
        # Create backup just in case
        if chunks_path.exists():
            backup_path = chunks_path.with_suffix(".json.before_update")
            import shutil
            shutil.copy2(chunks_path, backup_path)
            print(f"\n💾 Backup created: {backup_path.name}")

        chunker.save_chunks(merged_chunks)
        print(f"💾 Updated chunks.json saved! ({len(merged_chunks)} chunks)")
        
        if stats["new_or_modified"] > 0:
            print(f"\n👉 NEXT STEP: Run 'python setup_enrich.py' to enrich the {stats['new_or_modified']} new chunks.")

if __name__ == "__main__":
    main()
