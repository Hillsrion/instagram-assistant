#!/usr/bin/env python3
"""
Generate a dataset for enrichment evaluation by sampling chunks from the index.
Focuses on capturing a variety of complexities (Simple, Medium, Complex).

Usage:
    python -m eval.enrichment.generate_dataset [size]
    python -m eval.enrichment.generate_dataset 50
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import List, Dict

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker, Chunk
from rag_pipeline.complexity_analyzer import ChunkComplexityAnalyzer

def generate_enrichment_dataset(size: int = 50, output_file: str = "eval/enrichment/enrichment_eval_dataset.json"):
    """
    Generates a dataset of chunks for enrichment evaluation.
    Tries to balance between Simple, Medium, and Complex chunks.
    """
    config = Config()
    analyzer = ChunkComplexityAnalyzer(config)
    
    # 1. Load Chunks
    print("📂 Loading chunks from index...")
    chunker = ConversationChunker(config)
    all_chunks = chunker.load_chunks()
    
    if not all_chunks:
        print("❌ No chunks found in index. Please run indexing first.")
        sys.exit(1)
        
    print(f"✅ Loaded {len(all_chunks)} chunks.")
    
    # 2. Categorize Chunks
    buckets = {
        "simple": [],
        "medium": [],
        "complex": []
    }
    
    print("Start categorizing chunks...")
    
    for chunk in all_chunks:
        # Calculate scores if not present (though they should be if using the main pipeline)
        # We re-calculate to be sure we have the latest logic
        # Calculate scores if not present (though they should be if using the main pipeline)
        # We re-calculate to be sure we have the latest logic
        analysis = analyzer.analyze(chunk)
        category = analysis.category
        
        # Store essential data for the dataset
        # STRIP EXISTING ENRICHMENT: We want to test generation from scratch
        chunk_data = chunk.to_dict()
        
        # Clear enrichment fields
        chunk_data['narrative_summary'] = None
        chunk_data['hypothetical_questions'] = []
        chunk_data['speaker_intents'] = {}
        chunk_data['temporal_context'] = None
        chunk_data['entities'] = {}
        chunk_data['emotions'] = {}
        chunk_data['interaction_pattern'] = None
        chunk_data['initiative'] = None
        chunk_data['emotional_shift'] = None
        chunk_data['open_loops'] = []

        if chunk_data.get('metadata') is None:
            chunk_data['metadata'] = {}
            
        chunk_data['metadata']['complexity_category'] = category
        chunk_data['metadata']['complexity_score'] = analysis.score
        
        buckets[category].append(chunk_data)

    print(f"📊 Distribution: Simple: {len(buckets['simple'])}, Medium: {len(buckets['medium'])}, Complex: {len(buckets['complex'])}")
    
    # 3. Sample
    target_per_bucket = size // 3
    dataset = []
    
    for category, items in buckets.items():
        if len(items) > target_per_bucket:
            selected = random.sample(items, target_per_bucket)
        else:
            selected = items # Take all if not enough
        dataset.extend(selected)
        
    # Fill remainder if buckets were unbalanced
    if len(dataset) < size:
        remaining = size - len(dataset)
        # Flatten unselected items
        all_remaining = []
        for cat, items in buckets.items():
            used_ids = {x['chunk_id'] for x in dataset}
            all_remaining.extend([x for x in items if x['chunk_id'] not in used_ids])
            
        if all_remaining:
            dataset.extend(random.sample(all_remaining, min(len(all_remaining), remaining)))

    print(f"✅ Selected {len(dataset)} chunks for evaluation.")

    # 4. Save
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
        
    print(f"💾 Saved dataset to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate dataset for enrichment evaluation")
    parser.add_argument("size", type=int, nargs="?", default=50, help="Number of chunks to generate")
    parser.add_argument("--output", type=str, default="eval/enrichment/enrichment_eval_dataset.json", help="Output JSON file path")
    
    args = parser.parse_args()
    generate_enrichment_dataset(args.size, args.output)
