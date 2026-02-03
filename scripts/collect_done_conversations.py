#!/usr/bin/env python3
"""
Script to identify fully enriched conversations and save their IDs.
Enrichment is verified by checking if all chunks in a conversation
have narrative summaries and hypothetical questions.

The list of "done" IDs is saved to rag_data/chunk_done_conversations.
"""
import json
import argparse
from pathlib import Path
from collections import defaultdict

# Fields that indicate a chunk has been enriched
ENRICHMENT_FIELDS = [
    "narrative_summary",
    "hypothetical_questions"
]

def is_chunk_enriched(chunk: dict) -> bool:
    """Returns True if chunk has the required enrichment data."""
    for field in ENRICHMENT_FIELDS:
        value = chunk.get(field)
        if not value: # None, "", or []
            return False
    return True

def main():
    parser = argparse.ArgumentParser(description="Collect fully enriched conversation IDs")
    parser.add_argument("--output", type=str, default="rag_data/chunk_done_conversations", 
                        help="Path to the output file (default: rag_data/chunk_done_conversations)")
    args = parser.parse_args()

    chunks_path = Path("rag_data/chunks.json")
    output_path = Path(args.output)
    
    if not chunks_path.exists():
        print(f"❌ Error: {chunks_path} not found.")
        return

    print(f"📂 Loading chunks from {chunks_path}...")
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    print(f"📊 Analyzing {len(chunks)} chunks...")
    
    # Group chunks by conversation_id
    by_conversation = defaultdict(list)
    for chunk in chunks:
        conv_id = chunk.get("conversation_id")
        if conv_id:
            by_conversation[conv_id].append(chunk)
    
    total_convs = len(by_conversation)
    done_conversations = []
    partial_conversations = 0
    not_started_conversations = 0
    
    for conv_id, conv_chunks in by_conversation.items():
        enriched_count = sum(1 for c in conv_chunks if is_chunk_enriched(c))
        
        if enriched_count == len(conv_chunks):
            done_conversations.append(conv_id)
        elif enriched_count > 0:
            partial_conversations += 1
        else:
            not_started_conversations += 1
            
    # Create parent directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Sort for deterministic output
    done_conversations.sort()
    
    # Write to file (one ID per line)
    with open(output_path, "w", encoding="utf-8") as f:
        for conv_id in done_conversations:
            f.write(f"{conv_id}\n")
    
    print("\n" + "=" * 50)
    print("ENRICHMENT COMPLETION REPORT")
    print("=" * 50)
    print(f"Total Conversations:   {total_convs}")
    print(f"✅ Fully Enriched:     {len(done_conversations)}")
    print(f"🔄 Partially Enriched: {partial_conversations}")
    print(f"❌ Not Started:        {not_started_conversations}")
    print("-" * 50)
    print(f"💾 Saved {len(done_conversations)} IDs to: {output_path}")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    main()
