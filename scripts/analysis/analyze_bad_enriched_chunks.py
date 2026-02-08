from rag_pipeline.core.models import Chunk

import sys
import json
import os
from pathlib import Path
from dataclasses import asdict

# Add project root to path
sys.path.append(os.getcwd())

from rag_pipeline.core.config import default_config
from rag_pipeline.enrichment.enrichment_validator import is_low_quality_enrichment

def is_low_quality(chunk: Chunk) -> bool:
    """
    Detects if a chunk has low quality enrichment (sparse fields).
    Uses the logic from rag_pipeline.enrichment_validator.
    """
    # Convert chunk to the tuple format expected by the validator
    data = (
        chunk.narrative_summary,
        chunk.hypothetical_questions,
        chunk.speaker_intents,
        chunk.temporal_context,
        chunk.entities,
        chunk.emotions,
        chunk.interaction_pattern,
        chunk.initiative,
        chunk.emotional_shift,
        chunk.open_loops
    )
    return is_low_quality_enrichment(data)

def analyze_chunks():
    chunks_path = default_config.chunks_cache_path
    if not chunks_path.exists():
        print(f"❌ No chunks file found at {chunks_path}")
        return

    print(f"📂 Loading chunks from {chunks_path}...")
    try:
        with open(chunks_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        chunks = [Chunk.from_dict(d) for d in data]
    except Exception as e:
        print(f"❌ Failed to load chunks: {e}")
        return

    total = len(chunks)
    enriched_count = 0
    low_quality_count = 0
    failed_count = 0
    
    low_quality_chunks = []

    print(f"🔍 Analyzing {total} chunks...")

    for chunk in chunks:
        if chunk.enrichment_failed:
            failed_count += 1
            continue

        if chunk.narrative_summary:
            enriched_count += 1
            if is_low_quality(chunk):
                low_quality_count += 1
                low_quality_chunks.append(chunk)
        else:
            # No summary, but not marked as failed? 
            # Could be unenriched or legacy chunk.
            pass

    print("\n" + "="*50)
    print("📊 Analysis Results")
    print("="*50)
    print(f"Total Chunks:       {total}")
    print(f"Enriched:           {enriched_count}")
    print(f"Marked Failed:      {failed_count}")
    print(f"Low Quality:        {low_quality_count} ({low_quality_count/enriched_count*100:.1f}% of enriched)" if enriched_count > 0 else "Low Quality:        0")
    print("="*50)

    if low_quality_count > 0:
        print("\n⚠️  Sample Low Quality Chunks:")
        for i, chunk in enumerate(low_quality_chunks[:5]):
            print(f"- {chunk.chunk_id}: {chunk.narrative_summary[:100]}...")
            # Print which fields ARE populated
            fields = []
            if chunk.hypothetical_questions: fields.append("questions")
            if chunk.speaker_intents: fields.append("intents")
            if chunk.temporal_context: fields.append("time")
            if chunk.entities: fields.append("entities")
            if chunk.emotions: fields.append("emotions")
            print(f"  Populated: {', '.join(fields) if fields else 'None'}")
        
        output_file = Path("bad_chunks.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump([c.to_dict() for c in low_quality_chunks], f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved {len(low_quality_chunks)} low quality chunks to {output_file.absolute()}")

if __name__ == "__main__":
    analyze_chunks()
