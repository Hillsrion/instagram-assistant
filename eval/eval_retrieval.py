#!/usr/bin/env python3
"""
Evaluate RETRIEVAL quality of the RAG pipeline.

Tests whether the correct source chunks are retrieved for each question.
Measures: Hit@k (accuracy), MRR (ranking quality), and LLM-judged answer quality.

Usage:
    python -m eval.eval_retrieval
    python -m eval.eval_retrieval --question-type factual --difficulty easy
    python -m eval.eval_retrieval --judge qwen3:latest
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config

from .benchmark import BenchmarkRunner, BenchmarkConfig
from ._cli_utils import print_header, add_filter_arguments, parse_filters, load_qa_pairs


def run_benchmark(config: Config, filters: dict = None, judge_model: str = None):
    """
    Evaluate retrieval quality on existing dataset.

    Tests whether the RAG pipeline retrieves the correct source chunks.
    """
    print("Evaluating retrieval quality...")
    print()

    # Load and filter QA pairs
    qa_pairs = load_qa_pairs(config, filters)
    if not qa_pairs:
        return

    print()

    # Run benchmark
    runner = BenchmarkRunner(config)

    # Override judge model if specified
    if judge_model:
        runner.metrics.config.llm_model = judge_model
        print(f"Using judge model: {judge_model}")
        print()

    bench_config = BenchmarkConfig(
        name="default",
        use_query_rewriting=True,
        use_reranking=True,
        use_hybrid=True,
        use_context_expansion=True
    )

    def progress(curr, total, msg):
        print(f"  [{curr}/{total}] {msg[:60]}")

    report = runner.run_benchmark(qa_pairs, bench_config, progress_callback=progress)

    # Print results
    print()
    print(report.summary())

    # Save
    runner.save_report(report)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate RETRIEVAL quality: tests if correct chunks are retrieved for each question",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Metrics:
  - Hit@k: Percentage of questions where correct chunk is in top-k results
  - MRR: Mean Reciprocal Rank (ranking quality)
  - Faithfulness: LLM-judged answer fidelity to sources
  - Relevance: LLM-judged answer relevance to question

Examples:
    python -m eval.eval_retrieval
    python -m eval.eval_retrieval --question-type factual,summary
    python -m eval.eval_retrieval --difficulty easy,medium
    python -m eval.eval_retrieval --participant "Alice"
    python -m eval.eval_retrieval --judge qwen3:latest
        """
    )

    # Add filter arguments
    add_filter_arguments(parser)

    # Add judge model argument
    parser.add_argument(
        '--judge',
        type=str,
        metavar='MODEL',
        help='LLM model to use as judge for evaluation (default: from config)'
    )

    args = parser.parse_args()

    config = Config()

    print_header("RAG Evaluation - Retrieval Quality")

    filters = parse_filters(args)
    run_benchmark(config, filters, judge_model=args.judge)


if __name__ == "__main__":
    main()
