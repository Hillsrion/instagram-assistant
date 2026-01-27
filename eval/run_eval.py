#!/usr/bin/env python3
"""
CLI entry point for RAG evaluation.

Usage:
    python -m eval.run_eval --generate 50    # Generate 50 QA pairs
    python -m eval.run_eval --benchmark      # Run benchmark on existing dataset
    python -m eval.run_eval --compare        # Compare configurations
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.vector_store import VectorStore

from .synthetic_generator import SyntheticDataGenerator, QuestionFilter, QuestionType, Difficulty
from .benchmark import BenchmarkRunner, BenchmarkConfig


def generate_dataset(n_samples: int, config: Config):
    """Generate synthetic QA dataset."""
    print(f"Generating {n_samples} QA pairs...")
    print()

    # Load chunks
    vector_store = VectorStore(config)
    if not vector_store.load():
        print("⚠️ FAISS index not found. Trying to load chunks from cache...")
        from rag_pipeline.chunker import ConversationChunker
        chunker = ConversationChunker(config)
        chunks = chunker.load_chunks()
        if not chunks:
            print("Error: No chunks found in cache either. Run setup_rag_batch.py first.")
            return
        vector_store.chunks = chunks
        print(f"✅ Loaded {len(chunks)} chunks from cache")
    else:
        print(f"✅ Loaded {len(vector_store.chunks)} chunks from FAISS index")

    # Generate
    generator = SyntheticDataGenerator(config)

    def progress(curr, total, msg):
        print(f"  [{curr}/{total}] {msg}")

    qa_pairs = generator.generate_dataset(
        vector_store.chunks,
        target_size=n_samples,
        progress_callback=progress
    )

    # Save
    generator.save_dataset(qa_pairs)

    print()
    print(f"Generated {len(qa_pairs)} QA pairs")

    # Summary
    by_type = {}
    for qa in qa_pairs:
        t = qa.question_type.value
        by_type[t] = by_type.get(t, 0) + 1

    print("\nBy type:")
    for t, count in by_type.items():
        print(f"  {t}: {count}")


def run_benchmark(config: Config, filters: dict = None):
    """Run benchmark on existing dataset with optional filters."""
    print("Running benchmark...")
    print()

    # Load dataset
    generator = SyntheticDataGenerator(config)
    qa_pairs = generator.load_dataset()

    if not qa_pairs:
        print("Error: No evaluation dataset found. Run --generate first.")
        return

    print(f"Loaded {len(qa_pairs)} QA pairs")

    # Apply filters if provided
    if filters:
        original_count = len(qa_pairs)
        qa_pairs = QuestionFilter.apply_filters(qa_pairs, **filters)
        print(f"After filtering: {len(qa_pairs)} QA pairs")
        if not qa_pairs:
            print("Error: No QA pairs left after filtering.")
            return
        if len(qa_pairs) < original_count:
            print(f"  (filtered out {original_count - len(qa_pairs)} pairs)")

    print()

    # Run benchmark
    runner = BenchmarkRunner(config)

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


def run_comparison(config: Config, filters: dict = None):
    """Compare multiple configurations with optional filters."""
    print("Running configuration comparison...")
    print()

    # Load dataset
    generator = SyntheticDataGenerator(config)
    qa_pairs = generator.load_dataset()

    if not qa_pairs:
        print("Error: No evaluation dataset found. Run --generate first.")
        return

    print(f"Loaded {len(qa_pairs)} QA pairs")

    # Apply filters if provided
    if filters:
        original_count = len(qa_pairs)
        qa_pairs = QuestionFilter.apply_filters(qa_pairs, **filters)
        print(f"After filtering: {len(qa_pairs)} QA pairs")
        if not qa_pairs:
            print("Error: No QA pairs left after filtering.")
            return
        if len(qa_pairs) < original_count:
            print(f"  (filtered out {original_count - len(qa_pairs)} pairs)")

    print()

    # Run comparison
    runner = BenchmarkRunner(config)

    def progress(curr, total, msg):
        if curr == 0:
            print(f"\n{msg}")
        else:
            print(f"  [{curr}/{total}] {msg[:50]}", end="\r")

    reports = runner.compare_configs(qa_pairs, progress_callback=progress)

    print("\n")

    # Print comparison
    runner.print_comparison(reports)

    # Save
    runner.save_comparison(reports)


def main():
    parser = argparse.ArgumentParser(
        description="RAG Evaluation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m eval.run_eval --generate 50
    python -m eval.run_eval --benchmark
    python -m eval.run_eval --compare
    python -m eval.run_eval --benchmark --question-type factual,summary
    python -m eval.run_eval --benchmark --difficulty easy,medium
    python -m eval.run_eval --benchmark --participant "Alice"
        """
    )

    parser.add_argument(
        '--generate',
        type=int,
        metavar='N',
        help='Generate N synthetic QA pairs'
    )
    parser.add_argument(
        '--benchmark',
        action='store_true',
        help='Run benchmark on existing dataset'
    )
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Compare multiple configurations'
    )
    parser.add_argument(
        '--dataset',
        type=str,
        help='Path to custom evaluation dataset'
    )

    # Filter options
    parser.add_argument(
        '--question-type',
        type=str,
        metavar='TYPE[,TYPE...]',
        help=f'Filter by question type: {", ".join([t.value for t in QuestionType])}'
    )
    parser.add_argument(
        '--difficulty',
        type=str,
        metavar='LEVEL[,LEVEL...]',
        help=f'Filter by difficulty: {", ".join([d.value for d in Difficulty])}'
    )
    parser.add_argument(
        '--participant',
        type=str,
        metavar='NAME',
        help='Filter by participant name'
    )
    parser.add_argument(
        '--date-start',
        type=str,
        metavar='YYYY-MM-DD',
        help='Filter by date start (ISO format)'
    )
    parser.add_argument(
        '--date-end',
        type=str,
        metavar='YYYY-MM-DD',
        help='Filter by date end (ISO format)'
    )
    parser.add_argument(
        '--tags',
        type=str,
        metavar='TAG[,TAG...]',
        help='Filter by tags (comma-separated, must have all tags)'
    )

    args = parser.parse_args()

    if not any([args.generate, args.benchmark, args.compare]):
        parser.print_help()
        return

    config = Config()

    print("=" * 60)
    print("RAG Evaluation Pipeline")
    print("=" * 60)
    print()

    # Build filters dictionary
    filters = {}
    if args.question_type:
        filters['question_types'] = args.question_type.split(',')
    if args.difficulty:
        filters['difficulties'] = args.difficulty.split(',')
    if args.participant:
        filters['participant'] = args.participant
    if args.date_start and args.date_end:
        filters['start_date'] = args.date_start
        filters['end_date'] = args.date_end
    if args.tags:
        filters['tags'] = args.tags.split(',')

    if args.generate:
        generate_dataset(args.generate, config)
    elif args.benchmark:
        run_benchmark(config, filters if filters else None)
    elif args.compare:
        run_comparison(config, filters if filters else None)


if __name__ == "__main__":
    main()
