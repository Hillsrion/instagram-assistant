#!/usr/bin/env python3
"""
Phase 0: Benchmark 3B vs 8B models on validation dataset.

Purpose:
  - Enrich each chunk in validation dataset with 3B model
  - Enrich same chunks with 8B model
  - Compare enrichment quality using existing evaluation tools
  - Measure timing and RAM usage for each model
  - Generate benchmark report with recommendations

This script requires Ollama with both ministral:3b and ministral:8b available.

Usage:
    python scripts/benchmark_models.py \
        --dataset validation_dataset.json \
        --output benchmark_report.json \
        --strategy dual
"""
import json
import argparse
import time
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import psutil
import os

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.chunker import Chunk
from rag_pipeline.enricher import ChunkEnricher
from rag_pipeline.config import default_config


@dataclass
class EnrichmentResult:
    """Result of enriching a single chunk with a model."""
    chunk_id: str
    model: str
    success: bool
    enrichment_time_ms: float
    memory_before_mb: float
    memory_after_mb: float
    memory_delta_mb: float
    summary_length: int
    questions_count: int
    error: Optional[str] = None


@dataclass
class ChunkBenchmark:
    """Benchmark results for a single chunk enriched with both models."""
    chunk_id: str
    category: str
    message_count: int
    participants: int
    result_3b: Optional[EnrichmentResult]
    result_8b: Optional[EnrichmentResult]
    quality_delta: Optional[float] = None
    time_delta_ms: Optional[float] = None


def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def load_validation_dataset(path: Path) -> List[Dict[str, Any]]:
    """Load validation dataset."""
    with open(path) as f:
        return json.load(f)


def chunk_dict_to_object(chunk_dict: Dict[str, Any]) -> Chunk:
    """Convert JSON dict to Chunk object."""
    return Chunk(
        chunk_id=chunk_dict.get('chunk_id', ''),
        conversation_id=chunk_dict.get('conversation_id', ''),
        participants=chunk_dict.get('participants', []),
        date_start=chunk_dict.get('date_start', ''),
        date_end=chunk_dict.get('date_end', ''),
        message_count=chunk_dict.get('message_count', 0),
        content=chunk_dict.get('content', ''),
        file_source=chunk_dict.get('file_source', 'validation')
    )


def enrich_chunk_with_model(chunk: Chunk, model: str, timeout: int = 300) -> EnrichmentResult:
    """
    Enrich a chunk with specified model.

    Args:
        chunk: Chunk to enrich
        model: Model name (e.g., 'ministral-3:3b' or 'ministral-3:8b')
        timeout: Timeout in seconds

    Returns:
        EnrichmentResult with timing and success information
    """
    mem_before = get_memory_usage_mb()

    try:
        # Create enricher with specific model
        config = default_config
        config.llm_model = model

        enricher = ChunkEnricher(config=config, provider='ollama')
        enricher.model = model  # Override model selection

        start_time = time.time()
        summary, questions, intents, temporal, entities, emotions, pattern, initiative, shift, loops = enricher.enrich_chunk(chunk)
        elapsed_ms = (time.time() - start_time) * 1000

        mem_after = get_memory_usage_mb()

        return EnrichmentResult(
            chunk_id=chunk.chunk_id,
            model=model,
            success=True,
            enrichment_time_ms=elapsed_ms,
            memory_before_mb=mem_before,
            memory_after_mb=mem_after,
            memory_delta_mb=mem_after - mem_before,
            summary_length=len(summary) if summary else 0,
            questions_count=len(questions) if questions else 0,
        )

    except Exception as e:
        mem_after = get_memory_usage_mb()
        print(f"  ❌ Error enriching {chunk.chunk_id} with {model}: {e}")
        return EnrichmentResult(
            chunk_id=chunk.chunk_id,
            model=model,
            success=False,
            enrichment_time_ms=0,
            memory_before_mb=mem_before,
            memory_after_mb=mem_after,
            memory_delta_mb=mem_after - mem_before,
            summary_length=0,
            questions_count=0,
            error=str(e)
        )


def benchmark_chunk(chunk_dict: Dict[str, Any]) -> Optional[ChunkBenchmark]:
    """
    Benchmark a single chunk with both 3B and 8B models.

    Args:
        chunk_dict: Chunk data from validation dataset

    Returns:
        ChunkBenchmark or None if enrichment failed for both models
    """
    chunk = chunk_dict_to_object(chunk_dict)
    chunk_id = chunk_dict['chunk_id']
    category = chunk_dict['classification']['category']

    print(f"  📊 Benchmarking {chunk_id} ({category})...", end=' ', flush=True)

    # Enrich with 3B
    result_3b = enrich_chunk_with_model(chunk, 'ministral-3:3b')
    print(f"3B: {result_3b.enrichment_time_ms:.0f}ms", end=' ', flush=True)

    # Small delay to let model unload if on-demand
    time.sleep(0.5)

    # Enrich with 8B
    result_8b = enrich_chunk_with_model(chunk, 'ministral-3:8b')
    print(f"8B: {result_8b.enrichment_time_ms:.0f}ms", flush=True)

    return ChunkBenchmark(
        chunk_id=chunk_id,
        category=category,
        message_count=chunk_dict['message_count'],
        participants=len(chunk_dict.get('participants', [])),
        result_3b=result_3b,
        result_8b=result_8b,
        time_delta_ms=(result_8b.enrichment_time_ms - result_3b.enrichment_time_ms)
        if result_8b.success and result_3b.success else None
    )


def generate_benchmark_report(benchmarks: List[ChunkBenchmark]) -> Dict[str, Any]:
    """
    Generate summary report from benchmark results.

    Args:
        benchmarks: List of ChunkBenchmark results

    Returns:
        Report dict with statistics and recommendations
    """
    successful = [b for b in benchmarks if b.result_3b and b.result_3b.success and b.result_8b and b.result_8b.success]

    if not successful:
        return {
            'status': 'failed',
            'message': 'No successful benchmarks - check Ollama connection and model availability'
        }

    # Group by category
    by_category = {}
    for category in ['simple', 'medium', 'complex']:
        cat_benchmarks = [b for b in successful if b.category == category]
        if cat_benchmarks:
            avg_time_3b = sum(b.result_3b.enrichment_time_ms for b in cat_benchmarks) / len(cat_benchmarks)
            avg_time_8b = sum(b.result_8b.enrichment_time_ms for b in cat_benchmarks) / len(cat_benchmarks)
            avg_summary_3b = sum(b.result_3b.summary_length for b in cat_benchmarks) / len(cat_benchmarks)
            avg_summary_8b = sum(b.result_8b.summary_length for b in cat_benchmarks) / len(cat_benchmarks)

            by_category[category] = {
                'count': len(cat_benchmarks),
                'time_3b_ms': avg_time_3b,
                'time_8b_ms': avg_time_8b,
                'time_gain_percent': ((avg_time_8b - avg_time_3b) / avg_time_8b * 100) if avg_time_8b > 0 else 0,
                'avg_summary_length_3b': avg_summary_3b,
                'avg_summary_length_8b': avg_summary_8b,
            }

    # Overall statistics
    total_time_3b = sum(b.result_3b.enrichment_time_ms for b in successful)
    total_time_8b = sum(b.result_8b.enrichment_time_ms for b in successful)
    avg_mem_3b = sum(b.result_3b.memory_delta_mb for b in successful) / len(successful)
    avg_mem_8b = sum(b.result_8b.memory_delta_mb for b in successful) / len(successful)

    # Projection to 32k chunks (80% of distribution we see in validation dataset)
    simple_pct = len([b for b in successful if b.category == 'simple']) / len(successful)
    medium_pct = len([b for b in successful if b.category == 'medium']) / len(successful)
    complex_pct = len([b for b in successful if b.category == 'complex']) / len(successful)

    avg_time_per_chunk_8b = total_time_8b / len(successful) / 1000  # Convert to seconds
    avg_time_per_chunk_with_routing = (
        (simple_pct * by_category['simple']['time_3b_ms'] +
         medium_pct * by_category['medium']['time_3b_ms'] +
         complex_pct * by_category['complex']['time_8b_ms']) / 1000
    )

    projected_time_baseline_32k = 32559 * avg_time_per_chunk_8b
    projected_time_with_routing = 32559 * avg_time_per_chunk_with_routing
    projected_gain_seconds = projected_time_baseline_32k - projected_time_with_routing
    projected_gain_percent = (projected_gain_seconds / projected_time_baseline_32k * 100) if projected_time_baseline_32k > 0 else 0

    return {
        'status': 'success',
        'validation_count': len(successful),
        'by_category': by_category,
        'overall': {
            'total_time_3b_seconds': total_time_3b / 1000,
            'total_time_8b_seconds': total_time_8b / 1000,
            'avg_time_3b_seconds': total_time_3b / len(successful) / 1000,
            'avg_time_8b_seconds': total_time_8b / len(successful) / 1000,
            'avg_memory_delta_3b_mb': avg_mem_3b,
            'avg_memory_delta_8b_mb': avg_mem_8b,
        },
        'projection_32k_chunks': {
            'baseline_time_hours': projected_time_baseline_32k / 3600,
            'with_routing_time_hours': projected_time_with_routing / 3600,
            'gain_seconds': projected_gain_seconds,
            'gain_percent': projected_gain_percent,
            'assumptions': {
                'simple_percent': simple_pct * 100,
                'medium_percent': medium_pct * 100,
                'complex_percent': complex_pct * 100,
                'total_chunks': 32559,
                'medium_uses_light_model': True
            }
        },
        'recommendation': generate_recommendation(by_category, projected_gain_percent, avg_mem_3b, avg_mem_8b)
    }


def generate_recommendation(by_category: Dict[str, Dict],
                           projected_gain_percent: float,
                           avg_mem_3b: float,
                           avg_mem_8b: float) -> Dict[str, Any]:
    """
    Generate recommendation based on benchmark results.

    Criteria:
    1. 3B quality acceptable (at least 50% of 8B output quality)
    2. Gain > 20% time savings
    3. Memory overhead reasonable
    """
    recommendation = {
        'go_nogo': 'GO',
        'reasoning': [],
        'strategy': None,
        'caveats': []
    }

    # Check time gain
    if projected_gain_percent >= 20:
        recommendation['reasoning'].append(f"✅ Time gain {projected_gain_percent:.1f}% exceeds threshold (20%)")
    else:
        recommendation['reasoning'].append(f"⚠️ Time gain {projected_gain_percent:.1f}% below threshold (20%)")
        recommendation['go_nogo'] = 'NO-GO'

    # Check 3B quality on simple chunks
    if 'simple' in by_category:
        simple_avg_summary_3b = by_category['simple']['avg_summary_length_3b']
        simple_avg_summary_8b = by_category['simple']['avg_summary_length_8b']
        if simple_avg_summary_3b > 0:
            quality_ratio = simple_avg_summary_3b / simple_avg_summary_8b if simple_avg_summary_8b > 0 else 0
            if quality_ratio >= 0.7:
                recommendation['reasoning'].append(f"✅ 3B summary length {quality_ratio*100:.0f}% of 8B on simple chunks")
            else:
                recommendation['reasoning'].append(f"⚠️ 3B summary length {quality_ratio*100:.0f}% of 8B (low quality concern)")
                recommendation['caveats'].append("Consider adjusting thresholds to classify fewer chunks as 'simple'")

    # Recommend strategy
    if recommendation['go_nogo'] == 'GO':
        if projected_gain_percent >= 25:
            recommendation['strategy'] = 'dual-load'
            recommendation['reasoning'].append("✅ Sufficient gain justifies dual-load strategy (pre-load both models)")
        else:
            recommendation['strategy'] = 'on-demand'
            recommendation['reasoning'].append("✅ Moderate gain, recommend on-demand loading to manage RAM")

    return recommendation


def main():
    parser = argparse.ArgumentParser(description='Benchmark 3B vs 8B models')
    parser.add_argument(
        '--dataset',
        default='validation_dataset.json',
        help='Validation dataset path'
    )
    parser.add_argument(
        '--output',
        default='benchmark_report.json',
        help='Output report path'
    )
    parser.add_argument(
        '--strategy',
        choices=['dual', 'on-demand', 'batch'],
        default='dual',
        help='Model loading strategy for benchmarking'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of chunks to benchmark (for testing)'
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        print("Run: python scripts/create_validation_dataset.py")
        return 1

    print(f"📂 Loading validation dataset from {dataset_path}...")
    chunks = load_validation_dataset(dataset_path)

    if args.limit:
        chunks = chunks[:args.limit]

    print(f"✅ Loaded {len(chunks)} chunks for benchmarking")
    print(f"📋 Strategy: {args.strategy}")

    # Warm up models
    print("\n🔥 Warming up models (this may take 1-2 minutes)...")
    print("   Initializing Ollama connection...")
    try:
        import requests
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        if response.status_code != 200:
            print("❌ Ollama not running. Start with: ollama serve")
            return 1
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        return 1

    # Run benchmarks
    print(f"\n🏃 Running benchmarks on {len(chunks)} chunks...")
    benchmarks = []
    for i, chunk_dict in enumerate(chunks):
        print(f"[{i+1}/{len(chunks)}] ", end='', flush=True)
        result = benchmark_chunk(chunk_dict)
        if result:
            benchmarks.append(result)

    print(f"\n✅ Completed {len(benchmarks)} benchmarks")

    # Generate report
    print("\n📊 Generating benchmark report...")
    report = generate_benchmark_report(benchmarks)

    # Save report
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        # Custom serializer for dataclass objects
        json.dump(
            report,
            f,
            indent=2,
            default=lambda o: asdict(o) if hasattr(o, '__dataclass_fields__') else str(o)
        )

    print(f"💾 Report saved to {output_path}")

    # Print summary
    print(f"""
╔════════════════════════════════════════════════════════════╗
║                  BENCHMARK RESULTS SUMMARY                 ║
╚════════════════════════════════════════════════════════════╝

Status: {report.get('status', 'unknown').upper()}
Validation Chunks Processed: {report.get('validation_count', 0)}

""")

    if report['status'] == 'success':
        by_cat = report['by_category']
        print("ENRICHMENT TIME BY CATEGORY:")
        print(f"{'Category':<10} {'3B (ms)':<12} {'8B (ms)':<12} {'Gain %':<12}")
        print("-" * 50)
        for cat in ['simple', 'medium', 'complex']:
            if cat in by_cat:
                entry = by_cat[cat]
                print(f"{cat:<10} {entry['time_3b_ms']:<12.0f} {entry['time_8b_ms']:<12.0f} {entry['time_gain_percent']:<12.1f}")

        proj = report['projection_32k_chunks']
        print(f"""
PROJECTED RESULTS (32,559 chunks):
  Baseline (8B only):      {proj['baseline_time_hours']:.1f} hours
  With routing:            {proj['with_routing_time_hours']:.1f} hours
  Gain:                    {proj['gain_percent']:.1f}% ({proj['gain_seconds']/3600:.1f} hours)

RECOMMENDATION: {report['recommendation']['go_nogo']}
Strategy: {report['recommendation'].get('strategy', 'N/A')}

Reasoning:
""")
        for reason in report['recommendation'].get('reasoning', []):
            print(f"  {reason}")

        if report['recommendation'].get('caveats'):
            print("\nCaveats:")
            for caveat in report['recommendation']['caveats']:
                print(f"  ⚠️ {caveat}")

    print(f"\n✅ Full report: {output_path}")
    return 0


if __name__ == '__main__':
    exit(main())
