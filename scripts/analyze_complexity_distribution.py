#!/usr/bin/env python3
"""
Analyze complexity score distribution across all chunks.
Helps in tuning the thresholds for Simple/Medium/Complex categories.
"""

import sys
import numpy as np
from pathlib import Path
from collections import Counter

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.complexity_analyzer import ChunkComplexityAnalyzer

def analyze_distribution():
    config = Config()
    analyzer = ChunkComplexityAnalyzer(config)
    chunker = ConversationChunker(config)
    
    print("📂 Loading all chunks...")
    chunks = chunker.load_chunks()
    
    if not chunks:
        print("❌ No chunks found.")
        return

    print(f"✅ Loaded {len(chunks)} chunks. Analyzing complexity...")
    
    scores = []
    categories = []
    metrics_data = {
        "participants": [],
        "information_content": [],
        "media": [],
        "size": [],
        "dialogue": []
    }

    for chunk in chunks:
        if (chunk.message_count or 0) < 3: # Skip tiny chunks as per dataset gen
            continue
            
        analysis = analyzer.analyze(chunk)
        scores.append(analysis.score)
        categories.append(analysis.category)
        
        for k, v in analysis.breakdown.items():
            if k in metrics_data:
                metrics_data[k].append(v)
            
    scores = np.array(scores)
    
    print("\n" + "="*50)
    print("📊 COMPLEXITY SCORE DISTRIBUTION (Chunks with > 2 msgs)")
    print("="*50)
    print(f"Count: {len(scores)}")
    print(f"Min:   {scores.min():.4f}")
    print(f"Max:   {scores.max():.4f}")
    print(f"Mean:  {scores.mean():.4f}")
    print(f"Std:   {scores.std():.4f}")
    print("-" * 30)
    print("Percentiles:")
    for p in [10, 25, 50, 75, 90, 95, 99]:
        print(f"{p:>3}%:  {np.percentile(scores, p):.4f}")
        
    print("\n" + "="*50)
    print("📊 CATEGORY DISTRIBUTION (Current Thresholds)")
    print("="*50)
    print(f"Simple (< {analyzer.simple_threshold}):   {analyzer.simple_threshold}")
    print(f"Complex (>= {analyzer.complex_threshold}):  {analyzer.complex_threshold}")
    print("-" * 30)
    
    counts = Counter(categories)
    total = len(categories)
    for cat in ["simple", "medium", "complex"]:
        count = counts[cat]
        pct = (count / total) * 100
        print(f"{cat.capitalize():<10}: {count:>6} ({pct:>5.1f}%)")

    print("\n" + "="*50)
    print("📊 METRICS AVERAGES")
    print("="*50)
    for metric, values in metrics_data.items():
        print(f"{metric:<20}: {np.mean(values):.4f}")

if __name__ == "__main__":
    analyze_distribution()
