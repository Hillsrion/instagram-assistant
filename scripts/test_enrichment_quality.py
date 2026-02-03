#!/usr/bin/env python3
"""
Test enrichment quality and performance with real Ollama calls.

Tests:
1. Enrichment timing (3B vs 8B vs routed)
2. Output quality comparison
3. Routing accuracy
4. Error handling
5. Full performance projections

Usage:
    python scripts/test_enrichment_quality.py [--limit N] [--model MODEL]

Examples:
    # Test on 5 chunks
    python scripts/test_enrichment_quality.py --limit 5

    # Test specific model
    python scripts/test_enrichment_quality.py --limit 5 --model ministral-3:3b
"""
import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.chunker import Chunk
from rag_pipeline.enricher import ChunkEnricher
from rag_pipeline.config import Config
from rag_pipeline.complexity_analyzer import ChunkComplexityAnalyzer


def load_chunks(limit: int = 5) -> List[Chunk]:
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


def analyze_chunks(chunks: List[Chunk]) -> Dict:
    """Analyze chunk complexity distribution."""
    analyzer = ChunkComplexityAnalyzer()

    analyses = []
    for chunk in chunks:
        analysis = analyzer.analyze(chunk)
        analyses.append({
            "chunk_id": chunk.chunk_id,
            "score": analysis.score,
            "category": analysis.category,
            "metrics": analysis.metrics,
            "messages": chunk.message_count,
            "participants": len(chunk.participants or []),
        })

    categories = Counter(a["category"] for a in analyses)
    scores = [a["score"] for a in analyses]

    return {
        "analyses": analyses,
        "distribution": dict(categories),
        "avg_score": sum(scores) / len(scores) if scores else 0,
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
    }


def test_enrichment_timing(chunks: List[Chunk], model: str) -> Dict:
    """Test enrichment timing with a specific model."""
    config = Config()
    config.llm_model = model
    config.enable_complexity_routing = False
    enricher = ChunkEnricher(config=config)

    times = []
    summaries_len = []
    questions_count = []

    print(f"\n🔄 Testing enrichment with {model}...")
    print(f"   Processing {len(chunks)} chunks...")

    successful = 0
    failed = 0

    for i, chunk in enumerate(chunks):
        try:
            start = time.time()
            summary, questions, intents, temp_context, entities, emotions, pattern, initiative, shift, loops = \
                enricher.enrich_chunk(chunk)
            elapsed_ms = (time.time() - start) * 1000

            if summary:
                successful += 1
                times.append(elapsed_ms)
                summaries_len.append(len(summary))
                questions_count.append(len(questions) if questions else 0)
                print(f"   ✓ {i+1}/{len(chunks)} ({elapsed_ms:.0f}ms) - {len(summary)} chars, {len(questions)} Q")
            else:
                failed += 1
                print(f"   ✗ {i+1}/{len(chunks)} - Empty summary")

        except Exception as e:
            failed += 1
            print(f"   ✗ {i+1}/{len(chunks)} - Error: {str(e)[:50]}")

    avg_time = sum(times) / len(times) if times else 0
    avg_summary_len = sum(summaries_len) / len(summaries_len) if summaries_len else 0
    avg_questions = sum(questions_count) / len(questions_count) if questions_count else 0

    return {
        "model": model,
        "total": len(chunks),
        "successful": successful,
        "failed": failed,
        "times_ms": times,
        "avg_time_ms": avg_time,
        "min_time_ms": min(times) if times else 0,
        "max_time_ms": max(times) if times else 0,
        "avg_summary_len": avg_summary_len,
        "avg_questions": avg_questions,
    }


def test_routing(chunks: List[Chunk], complexity_data: Dict) -> Dict:
    """Test routing decisions on chunks."""
    config = Config()
    config.enable_complexity_routing = True
    enricher = ChunkEnricher(config=config)

    routing_decisions = []
    for analysis in complexity_data["analyses"]:
        chunk_id = analysis["chunk_id"]
        chunk = next((c for c in chunks if c.chunk_id == chunk_id), None)
        if not chunk:
            continue

        model = enricher._select_model_for_chunk(chunk)
        routing_decisions.append({
            "chunk_id": chunk_id,
            "score": analysis["score"],
            "category": analysis["category"],
            "model": model,
        })

    # Verify routing consistency
    for decision in routing_decisions:
        if decision["category"] == "simple":
            assert decision["model"] == "ministral-3:3b", \
                f"Simple chunks should route to 3B, got {decision['model']}"
        elif decision["category"] == "complex":
            assert decision["model"] == "ministral-3:8b", \
                f"Complex chunks should route to 8B, got {decision['model']}"

    model_usage = Counter(d["model"] for d in routing_decisions)

    return {
        "decisions": routing_decisions,
        "model_usage": dict(model_usage),
    }


def print_complexity_report(complexity_data: Dict):
    """Print complexity analysis report."""
    print("\n" + "="*70)
    print("📊 COMPLEXITY ANALYSIS REPORT")
    print("="*70)

    print(f"\nTotal chunks analyzed: {len(complexity_data['analyses'])}")
    print(f"Average complexity score: {complexity_data['avg_score']:.3f}")
    print(f"Score range: {complexity_data['min_score']:.3f} - {complexity_data['max_score']:.3f}")

    print(f"\nComplexity distribution:")
    for cat in ["simple", "medium", "complex"]:
        count = complexity_data["distribution"].get(cat, 0)
        pct = 100 * count / len(complexity_data["analyses"])
        print(f"  {cat:8}: {count:3} ({pct:5.1f}%)")

    print(f"\nPer-category breakdown:")
    for analysis in complexity_data["analyses"][:min(10, len(complexity_data["analyses"]))]:
        print(f"  {analysis['chunk_id']:20} {analysis['score']:.3f} "
              f"{analysis['category']:8} {analysis['messages']:3}msg {analysis['participants']:2}ppl")


def print_timing_report(results_by_model: Dict[str, Dict]):
    """Print enrichment timing report."""
    print("\n" + "="*70)
    print("⏱️  ENRICHMENT TIMING REPORT")
    print("="*70)

    print(f"\n{'Model':<20} {'Successful':<12} {'Avg Time':<12} {'Min':<10} {'Max':<10}")
    print("-" * 70)

    for model, result in results_by_model.items():
        if result["times_ms"]:
            print(f"{model:<20} {result['successful']:>11} {result['avg_time_ms']:>10.0f}ms "
                  f"{result['min_time_ms']:>8.0f}ms {result['max_time_ms']:>8.0f}ms")

    # Detailed comparison
    if len(results_by_model) > 1:
        models = sorted(results_by_model.keys())
        print(f"\nTiming comparison (relative to first model):")
        baseline_time = results_by_model[models[0]]["avg_time_ms"]

        for model in models:
            result = results_by_model[model]
            if result["times_ms"]:
                avg_time = result["avg_time_ms"]
                ratio = avg_time / baseline_time if baseline_time > 0 else 1.0
                print(f"  {model:<20}: {avg_time:7.0f}ms (x{ratio:.2f})")

    # Quality metrics
    print(f"\nOutput quality metrics:")
    for model, result in results_by_model.items():
        if result["successful"] > 0:
            print(f"  {model}:")
            print(f"    Avg summary length: {result['avg_summary_len']:.0f} chars")
            print(f"    Avg questions: {result['avg_questions']:.1f}")


def print_routing_report(routing_data: Dict, complexity_data: Dict):
    """Print routing analysis report."""
    print("\n" + "="*70)
    print("🛣️  ROUTING ANALYSIS REPORT")
    print("="*70)

    print(f"\nModel usage by routing:")
    total = sum(routing_data["model_usage"].values())
    for model, count in sorted(routing_data["model_usage"].items()):
        pct = 100 * count / total
        print(f"  {model:<30}: {count:3} chunks ({pct:5.1f}%)")

    # Show sample routing decisions
    print(f"\nSample routing decisions:")
    print(f"{'Chunk':<20} {'Score':<8} {'Category':<10} {'Routed to':<20}")
    print("-" * 70)
    for decision in routing_data["decisions"][:min(10, len(routing_data["decisions"]))]:
        print(f"{decision['chunk_id']:<20} {decision['score']:<8.3f} "
              f"{decision['category']:<10} {decision['model']:<20}")


def print_performance_projection(num_chunks: int, results_by_model: Dict[str, Dict]):
    """Print projected performance for full dataset."""
    print("\n" + "="*70)
    print("📈 PERFORMANCE PROJECTION")
    print("="*70)

    if num_chunks < 10:
        print("\nNote: Projection based on limited sample, may not be accurate")

    # Find 8B timing (baseline)
    baseline_result = None
    routed_result = None

    for model, result in results_by_model.items():
        if "8b" in model and not result.get("routed"):
            baseline_result = result
        if result.get("routed"):
            routed_result = result

    if baseline_result and baseline_result["times_ms"]:
        baseline_avg = baseline_result["avg_time_ms"]
        baseline_total_hours = (32559 * baseline_avg) / (1000 * 3600)

        print(f"\nBaseline (8B only):")
        print(f"  Per chunk: {baseline_avg:.0f}ms")
        print(f"  Total for 32,559 chunks: {baseline_total_hours:.1f} hours")

        if routed_result and routed_result["times_ms"]:
            routed_avg = routed_result["avg_time_ms"]
            routed_total_hours = (32559 * routed_avg) / (1000 * 3600)
            savings_hours = baseline_total_hours - routed_total_hours
            savings_pct = (savings_hours / baseline_total_hours) * 100

            print(f"\nWith intelligent routing:")
            print(f"  Per chunk: {routed_avg:.0f}ms")
            print(f"  Total for 32,559 chunks: {routed_total_hours:.1f} hours")
            print(f"  Savings: {savings_hours:.1f} hours ({savings_pct:.1f}%)")


def main():
    """Run all tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Test enrichment quality and performance")
    parser.add_argument("--limit", type=int, default=5, help="Number of chunks to test")
    parser.add_argument("--model", type=str, help="Test specific model only")
    parser.add_argument("--no-enrichment", action="store_true", help="Skip actual enrichment tests")

    args = parser.parse_args()

    print("="*70)
    print("🧪 ENRICHMENT QUALITY & PERFORMANCE TEST")
    print("="*70)

    # Step 1: Load chunks
    print(f"\n1️⃣  Loading chunks...")
    chunks = load_chunks(args.limit)
    if not chunks:
        print("❌ No chunks loaded")
        sys.exit(1)
    print(f"✅ Loaded {len(chunks)} chunks")

    # Step 2: Analyze complexity
    print(f"\n2️⃣  Analyzing complexity...")
    complexity_data = analyze_chunks(chunks)
    print_complexity_report(complexity_data)

    # Step 3: Test enrichment timing
    if not args.no_enrichment:
        print(f"\n3️⃣  Testing enrichment timing...")
        print(f"⚠️  This will take {args.limit * 30 // 60} - {args.limit * 45 // 60} minutes")
        print(f"    (each chunk takes ~30-45 seconds with Ollama)")

        results_by_model = {}

        if args.model:
            models = [args.model]
        else:
            models = ["ministral-3:3b", "ministral-3:8b"]

        for model in models:
            try:
                result = test_enrichment_timing(chunks, model)
                results_by_model[model] = result
            except Exception as e:
                print(f"❌ Error testing {model}: {e}")

        print_timing_report(results_by_model)

        # Step 4: Test routing
        print(f"\n4️⃣  Testing routing decisions...")
        routing_data = test_routing(chunks, complexity_data)
        print_routing_report(routing_data, complexity_data)

        # Step 5: Performance projection
        print(f"\n5️⃣  Performance projection...")
        print_performance_projection(len(chunks), results_by_model)
    else:
        print(f"\n3️⃣  Skipping enrichment tests (use --no-enrichment=false to run)")

    print("\n" + "="*70)
    print("✅ TEST COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
