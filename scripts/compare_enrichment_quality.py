#!/usr/bin/env python3
"""
Compare enrichment quality between 3B and 8B models using eval framework.

Tests actual enrichment output quality by:
1. Enriching same chunks with both 3B and 8B models
2. Using generation eval framework to measure quality
3. Comparing faithfulness, relevance, and other metrics
4. Providing recommendations for routing thresholds

Usage:
    python scripts/compare_enrichment_quality.py [--limit N]

Examples:
    # Compare on 3 chunks (quick test, ~2-3 minutes)
    python scripts/compare_enrichment_quality.py --limit 3

    # Compare on 10 chunks (full test, ~30 minutes)
    python scripts/compare_enrichment_quality.py --limit 10
"""
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.chunker import Chunk
from rag_pipeline.enricher import ChunkEnricher
from rag_pipeline.config import Config
from rag_pipeline.complexity_analyzer import ChunkComplexityAnalyzer


def load_chunks(limit: int = 3) -> List[Chunk]:
    """Load chunks from cache."""
    chunks_path = Path(__file__).parent.parent / "rag_data" / "chunks.json"

    if not chunks_path.exists():
        print(f"❌ chunks.json not found at {chunks_path}")
        print("   Run: python setup_rag.py --limit 100")
        sys.exit(1)

    with open(chunks_path) as f:
        chunks_data = json.load(f)

    chunks = []
    for chunk_data in chunks_data[:limit]:
        try:
            chunk = Chunk.from_dict(chunk_data)
            chunks.append(chunk)
        except Exception as e:
            print(f"⚠️  Could not load chunk: {e}")

    return chunks


def enrich_with_model(chunks: List[Chunk], model: str) -> Dict[str, Dict]:
    """Enrich chunks with a specific model."""
    config = Config()
    config.llm_model = model
    config.enable_complexity_routing = False
    enricher = ChunkEnricher(config=config)

    enriched = {}
    successful = 0
    failed = 0

    print(f"\n{'='*70}")
    print(f"Enriching with {model}")
    print(f"{'='*70}")

    for i, chunk in enumerate(chunks):
        try:
            start = time.time()
            summary, questions, intents, temp_context, entities, emotions, pattern, initiative, shift, loops = \
                enricher.enrich_chunk(chunk)
            elapsed_ms = (time.time() - start) * 1000

            if summary:
                successful += 1
                enriched[chunk.chunk_id] = {
                    "chunk": chunk,
                    "summary": summary,
                    "questions": questions,
                    "speaker_intents": intents,
                    "temporal_context": temp_context,
                    "entities": entities,
                    "emotions": emotions,
                    "interaction_pattern": pattern,
                    "initiative": initiative,
                    "emotional_shift": shift,
                    "open_loops": loops,
                    "enrichment_time_ms": elapsed_ms,
                }
                print(f"✓ {i+1}/{len(chunks)} ({elapsed_ms:.0f}ms) - {len(summary)} chars, "
                      f"{len(questions)} questions")
            else:
                failed += 1
                print(f"✗ {i+1}/{len(chunks)} - Empty summary")

        except Exception as e:
            failed += 1
            print(f"✗ {i+1}/{len(chunks)} - Error: {str(e)[:60]}")

    print(f"\nResults: {successful} successful, {failed} failed")
    return enriched


def compare_enrichments(enriched_3b: Dict, enriched_8b: Dict) -> Dict:
    """Compare enrichment quality between models."""
    print(f"\n{'='*70}")
    print("QUALITY COMPARISON: 3B vs 8B")
    print(f"{'='*70}")

    comparison = {}
    valid_chunks = set(enriched_3b.keys()) & set(enriched_8b.keys())

    print(f"\nComparing {len(valid_chunks)} chunks with both models...")

    metrics = defaultdict(list)

    for chunk_id in valid_chunks:
        data_3b = enriched_3b[chunk_id]
        data_8b = enriched_8b[chunk_id]

        # Basic metrics
        summary_3b_len = len(data_3b["summary"])
        summary_8b_len = len(data_8b["summary"])
        questions_3b = len(data_3b["questions"] or [])
        questions_8b = len(data_8b["questions"] or [])
        entities_3b = sum(len(v or []) for v in (data_3b.get("entities") or {}).values())
        entities_8b = sum(len(v or []) for v in (data_8b.get("entities") or {}).values())

        comparison[chunk_id] = {
            "summary_3b_len": summary_3b_len,
            "summary_8b_len": summary_8b_len,
            "questions_3b": questions_3b,
            "questions_8b": questions_8b,
            "entities_3b": entities_3b,
            "entities_8b": entities_8b,
            "time_3b_ms": data_3b["enrichment_time_ms"],
            "time_8b_ms": data_8b["enrichment_time_ms"],
        }

        metrics["summary_len_3b"].append(summary_3b_len)
        metrics["summary_len_8b"].append(summary_8b_len)
        metrics["questions_3b"].append(questions_3b)
        metrics["questions_8b"].append(questions_8b)
        metrics["entities_3b"].append(entities_3b)
        metrics["entities_8b"].append(entities_8b)
        metrics["time_3b"].append(data_3b["enrichment_time_ms"])
        metrics["time_8b"].append(data_8b["enrichment_time_ms"])

    # Print detailed comparison
    print(f"\n{'Chunk':<25} {'3B Summary':<15} {'8B Summary':<15} {'3B Q':<8} {'8B Q':<8}")
    print("-" * 75)

    for chunk_id in list(valid_chunks)[:min(5, len(valid_chunks))]:
        c = comparison[chunk_id]
        print(f"{chunk_id:<25} {c['summary_3b_len']:<15} {c['summary_8b_len']:<15} "
              f"{c['questions_3b']:<8} {c['questions_8b']:<8}")

    # Aggregate metrics
    print(f"\n{'METRIC':<30} {'3B':<15} {'8B':<15} {'Difference':<15}")
    print("-" * 75)

    avg_summary_3b = sum(metrics["summary_len_3b"]) / len(metrics["summary_len_3b"]) if metrics["summary_len_3b"] else 0
    avg_summary_8b = sum(metrics["summary_len_8b"]) / len(metrics["summary_len_8b"]) if metrics["summary_len_8b"] else 0
    avg_questions_3b = sum(metrics["questions_3b"]) / len(metrics["questions_3b"]) if metrics["questions_3b"] else 0
    avg_questions_8b = sum(metrics["questions_8b"]) / len(metrics["questions_8b"]) if metrics["questions_8b"] else 0
    avg_time_3b = sum(metrics["time_3b"]) / len(metrics["time_3b"]) if metrics["time_3b"] else 0
    avg_time_8b = sum(metrics["time_8b"]) / len(metrics["time_8b"]) if metrics["time_8b"] else 0

    print(f"Avg Summary Length      {avg_summary_3b:<15.0f} {avg_summary_8b:<15.0f} "
          f"{avg_summary_8b - avg_summary_3b:+.0f}")
    print(f"Avg Questions Generated {avg_questions_3b:<15.1f} {avg_questions_8b:<15.1f} "
          f"{avg_questions_8b - avg_questions_3b:+.1f}")
    print(f"Avg Enrichment Time     {avg_time_3b:<15.0f}ms {avg_time_8b:<15.0f}ms "
          f"{avg_time_8b - avg_time_3b:+.0f}ms")

    speedup = avg_time_8b / avg_time_3b if avg_time_3b > 0 else 1.0
    time_saved_pct = ((avg_time_8b - avg_time_3b) / avg_time_8b * 100) if avg_time_8b > 0 else 0

    print(f"\nPerformance Analysis:")
    print(f"  3B Speed: {speedup:.2f}x faster than 8B")
    print(f"  Time saved per chunk: {time_saved_pct:.1f}%")

    # Quality assessment
    print(f"\nQuality Assessment:")
    quality_3b = ((avg_summary_3b / avg_summary_8b) if avg_summary_8b > 0 else 1.0) * 0.6 + \
                 ((avg_questions_3b / avg_questions_8b) if avg_questions_8b > 0 else 1.0) * 0.4
    print(f"  3B quality ratio vs 8B: {quality_3b:.1%} of 8B")

    if quality_3b >= 0.70:
        print(f"  ✅ 3B quality is acceptable (≥70% of 8B)")
        print(f"  ✅ RECOMMENDATION: Route to 3B for speed gains")
    else:
        print(f"  ⚠️  3B quality is lower (<70% of 8B)")
        print(f"  ⚠️  RECOMMENDATION: Consider using 8B for quality")

    return {
        "comparison": comparison,
        "metrics": dict(metrics),
        "quality_ratio": quality_3b,
        "speedup": speedup,
    }


def print_routing_recommendations(quality_data: Dict, chunks: List[Chunk]):
    """Print routing recommendations based on quality data."""
    print(f"\n{'='*70}")
    print("ROUTING RECOMMENDATIONS")
    print(f"{'='*70}")

    quality_ratio = quality_data["quality_ratio"]
    speedup = quality_data["speedup"]

    print(f"\nQuality vs Speed Trade-off:")
    print(f"  3B Output Quality: {quality_ratio:.1%} of 8B")
    print(f"  Speed Gain: {(speedup - 1) * 100:.1f}% faster")

    # Full dataset projection
    avg_time_8b = sum(quality_data["metrics"]["time_8b"]) / len(quality_data["metrics"]["time_8b"])
    avg_time_3b = sum(quality_data["metrics"]["time_3b"]) / len(quality_data["metrics"]["time_3b"])

    baseline_hours = (32559 * avg_time_8b) / (1000 * 3600)
    routed_hours = (32559 * avg_time_3b) / (1000 * 3600)
    saved_hours = baseline_hours - routed_hours

    print(f"\nFull Dataset Projection (32,559 chunks):")
    print(f"  Baseline (8B only): {baseline_hours:.1f} hours")
    print(f"  With 3B routing:    {routed_hours:.1f} hours")
    print(f"  Time saved:         {saved_hours:.1f} hours ({saved_hours/baseline_hours*100:.1f}%)")

    print(f"\nRecommendation:")
    if quality_ratio >= 0.70:
        print(f"  ✅ GO: Route simple chunks to 3B model")
        print(f"     Expected time savings: {saved_hours:.1f} hours")
        print(f"     Quality acceptable: {quality_ratio:.1%} of 8B")
        print(f"\n  Suggested thresholds:")
        print(f"     - Simple chunks (< 0.35): Use 3B")
        print(f"     - Medium chunks (0.35-0.65): Use 3B (acceptable quality)")
        print(f"     - Complex chunks (≥ 0.65): Use 8B (quality critical)")
    else:
        print(f"  ⚠️  NO-GO: 3B quality is insufficient ({quality_ratio:.1%})")
        print(f"     Suggested alternatives:")
        print(f"     1. Use 8B only (no routing)")
        print(f"     2. Route only very simple chunks to 3B")
        print(f"     3. Test with quantized 8B model")


def main():
    """Run comparison."""
    import argparse

    parser = argparse.ArgumentParser(description="Compare 3B vs 8B enrichment quality")
    parser.add_argument("--limit", type=int, default=3,
                       help="Number of chunks to test (default: 3, ~2-3 min)")

    args = parser.parse_args()

    if args.limit < 2:
        print("❌ Need at least 2 chunks for comparison")
        sys.exit(1)

    print("="*70)
    print("🧪 ENRICHMENT QUALITY COMPARISON TEST")
    print("="*70)
    print(f"⏱️  Estimated time: {args.limit * 1} - {args.limit * 1.5} minutes")
    print(f"   (each chunk takes ~30-45 seconds per model with Ollama)")

    # Step 1: Load chunks
    print(f"\n1️⃣  Loading chunks...")
    chunks = load_chunks(args.limit)
    if not chunks:
        print("❌ No chunks loaded")
        sys.exit(1)
    print(f"✅ Loaded {len(chunks)} chunks")

    # Step 2: Analyze complexity
    print(f"\n2️⃣  Analyzing complexity...")
    analyzer = ChunkComplexityAnalyzer()
    for chunk in chunks:
        analysis = analyzer.analyze(chunk)
        print(f"  {chunk.chunk_id}: score={analysis.score:.3f}, "
              f"category={analysis.category}, messages={chunk.message_count}")

    # Step 3: Enrich with 3B
    print(f"\n3️⃣  Enriching with 3B model...")
    print(f"⏰  This will take ~{args.limit * 0.5} to {args.limit * 0.75} minutes...")
    enriched_3b = enrich_with_model(chunks, "ministral-3:3b")

    # Step 4: Enrich with 8B
    print(f"\n4️⃣  Enriching with 8B model...")
    print(f"⏰  This will take ~{args.limit * 0.5} to {args.limit * 0.75} minutes...")
    enriched_8b = enrich_with_model(chunks, "ministral-3:8b")

    # Step 5: Compare
    print(f"\n5️⃣  Comparing quality...")
    quality_data = compare_enrichments(enriched_3b, enriched_8b)

    # Step 6: Recommendations
    print_routing_recommendations(quality_data, chunks)

    print(f"\n{'='*70}")
    print("✅ COMPARISON COMPLETE")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
