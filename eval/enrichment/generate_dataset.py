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

from rag_pipeline.core.config import Config
from rag_pipeline.indexing.chunker import ConversationChunker
from rag_pipeline.core.models import Chunk
from rag_pipeline.enrichment.complexity_analyzer import ChunkComplexityAnalyzer

def generate_enrichment_dataset(
    size: int = 100, 
    output_file: str = "eval/enrichment/enrichment_eval_dataset.json",
    simple_target: int = None,
    medium_target: int = None,
    complex_target: int = None
):
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
        # Filter: at least 3 messages for meaningful enrichment evaluation
        if (chunk.message_count or 0) < 3:
            continue
            
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

    print(f"📊 Total available: Simple: {len(buckets['simple'])}, Medium: {len(buckets['medium'])}, Complex: {len(buckets['complex'])}")
    
    # 3. Sample with redistribution for under-represented categories
    available = {cat: len(buckets[cat]) for cat in buckets}
    
    # Initialize targets based on size
    if simple_target is None and medium_target is None and complex_target is None:
        # Calculate proportional targets based on available distribution
        total_available = sum(available.values())
        if total_available == 0:
            print("❌ No chunks available to sample from.")
            sys.exit(1)
            
        targets = {}
        remaining_size = size
        
        # Calculate targets for first two categories
        for cat in ["simple", "medium"]:
            proportion = available[cat] / total_available
            target = int(size * proportion)
            targets[cat] = target
            remaining_size -= target
            
        # Assign remainder to complex to ensure sum equals size
        targets["complex"] = remaining_size
    else:
        targets = {
            "simple": simple_target or 0,
            "medium": medium_target or 0,
            "complex": complex_target or 0
        }

    # Redistribution Loop: if a category has fewer items than its target,
    # redistribute the surplus to other categories that still have room.
    print(f"🎯 Initial targets: {targets}")
    for _ in range(5): # Rounds to stabilize redistribution
        total_overflow = 0
        cats_with_room = []
        
        for cat in ["simple", "medium", "complex"]:
            if targets[cat] > available[cat]:
                total_overflow += targets[cat] - available[cat]
                targets[cat] = available[cat]
            elif available[cat] > targets[cat]:
                cats_with_room.append(cat)
        
        if total_overflow <= 0 or not cats_with_room:
            break
            
        extra_per_cat = total_overflow // len(cats_with_room)
        remainder = total_overflow % len(cats_with_room)
        
        for i, cat in enumerate(cats_with_room):
            add = extra_per_cat + (1 if i < remainder else 0)
            targets[cat] += add

    print(f"📊 Final targets after redistribution: {targets}")
    
    dataset = []
    
    # 3a. Simple sampling (random)
    if targets["simple"] > 0:
        dataset.extend(random.sample(buckets["simple"], targets["simple"]))

    # 3b. Diversified sampling for medium and complex chunks
    weights = analyzer.weights
    
    def get_diversified_sample(items: List[dict], target: int, cat_name: str) -> List[dict]:
        if not items or target <= 0:
            return []
        
        if len(items) <= target:
            return items
            
        print(f"🎯 Performing diversified sampling for {target} {cat_name} chunks...")
        
        # Sub-bucket chunks by their dominant metric
        sub_buckets = {}
        for chunk_data in items:
            c = Chunk(**{k: v for k, v in chunk_data.items() if k != 'metadata'})
            analysis = analyzer.analyze(c)
            dominant_metric = max(weights.keys(), key=lambda m: analysis.breakdown[m] * weights[m])
            
            if dominant_metric not in sub_buckets:
                sub_buckets[dominant_metric] = []
            sub_buckets[dominant_metric].append(chunk_data)
            
        selected = []
        while len(selected) < target and sub_buckets:
            for m in list(sub_buckets.keys()):
                if len(selected) >= target:
                    break
                idx = random.randrange(len(sub_buckets[m]))
                selected.append(sub_buckets[m].pop(idx))
                if not sub_buckets[m]:
                    del sub_buckets[m]
        return selected

    dataset.extend(get_diversified_sample(buckets["medium"], targets["medium"], "medium"))
    dataset.extend(get_diversified_sample(buckets["complex"], targets["complex"], "complex"))

    # Shuffle the final dataset
    random.shuffle(dataset)

    print(f"✅ Selected {len(dataset)} chunks total for evaluation.")
    
    # Print final category counts
    final_counts = {"simple": 0, "medium": 0, "complex": 0}
    for item in dataset:
        final_counts[item['metadata']['complexity_category']] += 1
    print(f"📊 Final Sample Distribution: {final_counts}")

    # 4. Save
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
        
    print(f"💾 Saved dataset to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate dataset for enrichment evaluation")
    parser.add_argument("size", type=int, nargs="?", default=100, help="Total number of chunks to generate")
    parser.add_argument("--simple", type=int, help="Target number of simple chunks")
    parser.add_argument("--medium", type=int, help="Target number of medium chunks")
    parser.add_argument("--complex", type=int, help="Target number of complex chunks")
    parser.add_argument("--output", type=str, default="eval/enrichment/enrichment_eval_dataset.json", help="Output JSON file path")
    
    args = parser.parse_args()
    
    # If specific targets are provided, size should be the sum of targets if not explicitly set high enough
    if args.simple or args.medium or args.complex:
        total_target = (args.simple or 0) + (args.medium or 0) + (args.complex or 0)
        if total_target > args.size:
            args.size = total_target

    generate_enrichment_dataset(
        args.size, 
        args.output,
        simple_target=args.simple,
        medium_target=args.medium,
        complex_target=args.complex
    )
