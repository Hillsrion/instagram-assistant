#!/usr/bin/env python3
"""
Phase 0: Analyze benchmark report and determine GO/NO-GO decision.

This script reads the benchmark report and provides detailed analysis
with visualization and decision guidance.
"""
import json
import argparse
from pathlib import Path
from typing import Dict, Any


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def analyze_report(report: Dict[str, Any]):
    """Analyze and pretty-print the benchmark report."""

    if report['status'] != 'success':
        print(f"❌ Benchmark failed: {report.get('message', 'Unknown error')}")
        return False

    print_section("BENCHMARK RESULTS - COMPLEXITY ANALYSIS")

    # === TIMING ANALYSIS ===
    print_section("1. ENRICHMENT TIMING ANALYSIS")

    by_cat = report['by_category']
    total_benchmarks = sum(entry['count'] for entry in by_cat.values())

    print(f"Total chunks benchmarked: {total_benchmarks}")
    print(f"\n{'Category':<12} {'Count':<8} {'3B (ms)':<12} {'8B (ms)':<12} {'Gain %':<12} {'Speedup':<10}")
    print("-" * 70)

    total_time_3b = 0
    total_time_8b = 0

    for cat in ['simple', 'medium', 'complex']:
        if cat in by_cat:
            entry = by_cat[cat]
            time_3b = entry['time_3b_ms']
            time_8b = entry['time_8b_ms']
            gain = entry['time_gain_percent']
            speedup = time_8b / time_3b if time_3b > 0 else 0

            total_time_3b += time_3b * entry['count']
            total_time_8b += time_8b * entry['count']

            print(f"{cat:<12} {entry['count']:<8} {time_3b:<12.0f} {time_8b:<12.0f} {gain:<12.1f} {speedup:<10.2f}x")

    avg_time_3b = total_time_3b / total_benchmarks if total_benchmarks > 0 else 0
    avg_time_8b = total_time_8b / total_benchmarks if total_benchmarks > 0 else 0
    overall_gain = ((avg_time_8b - avg_time_3b) / avg_time_8b * 100) if avg_time_8b > 0 else 0

    print("-" * 70)
    print(f"{'AVERAGE':<12} {total_benchmarks:<8} {avg_time_3b:<12.0f} {avg_time_8b:<12.0f} {overall_gain:<12.1f} {avg_time_8b/avg_time_3b:<10.2f}x")

    # === QUALITY ANALYSIS ===
    print_section("2. OUTPUT QUALITY ANALYSIS")

    print("Average summary length (proxy for enrichment depth):")
    print(f"{'Category':<12} {'3B (chars)':<15} {'8B (chars)':<15} {'Ratio':<12}")
    print("-" * 54)

    for cat in ['simple', 'medium', 'complex']:
        if cat in by_cat:
            entry = by_cat[cat]
            len_3b = entry['avg_summary_length_3b']
            len_8b = entry['avg_summary_length_8b']
            ratio = (len_3b / len_8b * 100) if len_8b > 0 else 0
            print(f"{cat:<12} {len_3b:<15.0f} {len_8b:<15.0f} {ratio:<12.0f}%")

    # === PROJECTION ANALYSIS ===
    print_section("3. FULL INDEXING PROJECTION (32,559 chunks)")

    proj = report['projection_32k_chunks']
    assumptions = proj['assumptions']

    print("Dataset composition (from validation sample):")
    print(f"  Simple chunks:  {assumptions['simple_percent']:.1f}% ({int(32559 * assumptions['simple_percent']/100)} chunks)")
    print(f"  Medium chunks:  {assumptions['medium_percent']:.1f}% ({int(32559 * assumptions['medium_percent']/100)} chunks)")
    print(f"  Complex chunks: {assumptions['complex_percent']:.1f}% ({int(32559 * assumptions['complex_percent']/100)} chunks)")

    print(f"\nIndexing time estimate:")
    print(f"  Baseline (8B only):        {proj['baseline_time_hours']:.2f} hours ({proj['baseline_time_hours']*60:.0f} minutes)")
    print(f"  With intelligent routing:  {proj['with_routing_time_hours']:.2f} hours ({proj['with_routing_time_hours']*60:.0f} minutes)")
    print(f"  Time saved:                {proj['gain_seconds']/3600:.2f} hours ({proj['gain_seconds']/60:.0f} minutes)")
    print(f"  Improvement:               {proj['gain_percent']:.1f}%")

    # === RECOMMENDATION ===
    print_section("4. GO/NO-GO DECISION")

    rec = report['recommendation']
    decision = rec['go_nogo']

    if decision == 'GO':
        status_icon = "✅"
        color_code = "\033[92m"  # Green
    else:
        status_icon = "❌"
        color_code = "\033[91m"  # Red

    reset_code = "\033[0m"

    print(f"{color_code}DECISION: {status_icon} {decision}{reset_code}\n")
    print(f"Strategy: {rec.get('strategy', 'N/A')}")
    print(f"\nReasoning:")
    for reason in rec.get('reasoning', []):
        print(f"  {reason}")

    if rec.get('caveats'):
        print(f"\nCaveats:")
        for caveat in rec['caveats']:
            print(f"  ⚠️ {caveat}")

    # === NEXT STEPS ===
    print_section("5. NEXT STEPS")

    if decision == 'GO':
        print("""
✅ Complexity-based routing is recommended!

Next steps:
  1. Implement Phase 1: ChunkComplexityAnalyzer
     - Create: rag_pipeline/complexity_analyzer.py
     - Implement metrics calculation and classification

  2. Integrate into ChunkEnricher
     - Modify: rag_pipeline/enricher.py
     - Add model routing logic
     - Implement loading strategy

  3. Update Configuration
     - Modify: rag_pipeline/config.py
     - Add routing parameters and strategy options

  4. Add Logging and Metrics
     - Create: rag_pipeline/enrichment_log.py
     - Track routing decisions and quality

  5. Test on small batch
     - Run: python setup_rag.py --limit 500 --reset
     - Verify routing decisions and output quality

  6. Full indexing
     - Run: python setup_rag.py
     - Monitor enrichment progress and model switching overhead
""")
    else:
        print("""
❌ Complexity-based routing not recommended at this time.

Alternative approaches to explore:
  1. Quantized models: Use Q4 quantization instead of F16
     - Lower memory footprint, faster inference
     - Example: ministral-3:8b-instruct-2512-4bit

  2. Batch processing optimization:
     - Increase chunk batch size
     - Optimize prompt templates for faster generation

  3. Prompt optimization:
     - Reduce enrichment fields (fewer outputs = faster LLM)
     - Focus on highest-value enrichments

  4. Caching strategies:
     - Cache similar chunk enrichments
     - Batch chunks with similar content patterns

  5. Benchmark other models:
     - Compare with Qwen, Llama3, or other open-source models
     - Some models may be faster at same quality level
""")

    return decision == 'GO'


def main():
    parser = argparse.ArgumentParser(description='Analyze benchmark report')
    parser.add_argument(
        'report_path',
        nargs='?',
        default='benchmark_report.json',
        help='Path to benchmark report JSON'
    )
    args = parser.parse_args()

    report_path = Path(args.report_path)
    if not report_path.exists():
        print(f"❌ Report not found: {report_path}")
        print("Run: python scripts/benchmark_models.py")
        return 1

    print(f"📂 Loading benchmark report from {report_path}...")
    with open(report_path) as f:
        report = json.load(f)

    is_go = analyze_report(report)
    return 0 if is_go else 1


if __name__ == '__main__':
    exit(main())
