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

from .synthetic_generator import SyntheticDataGenerator
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


def run_benchmark(config: Config):
    """Run benchmark on existing dataset."""
    print("Running benchmark...")
    print()

    # Load dataset
    generator = SyntheticDataGenerator(config)
    qa_pairs = generator.load_dataset()

    if not qa_pairs:
        print("Error: No evaluation dataset found. Run --generate first.")
        return

    print(f"Loaded {len(qa_pairs)} QA pairs")

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


def run_comparison(config: Config):
    """Compare multiple configurations."""
    print("Running configuration comparison...")
    print()

    # Load dataset
    generator = SyntheticDataGenerator(config)
    qa_pairs = generator.load_dataset()

    if not qa_pairs:
        print("Error: No evaluation dataset found. Run --generate first.")
        return

    print(f"Loaded {len(qa_pairs)} QA pairs")
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

    args = parser.parse_args()

    if not any([args.generate, args.benchmark, args.compare]):
        parser.print_help()
        return

    config = Config()

    print("=" * 60)
    print("RAG Evaluation Pipeline")
    print("=" * 60)
    print()

    if args.generate:
        generate_dataset(args.generate, config)
    elif args.benchmark:
        run_benchmark(config)
    elif args.compare:
        run_comparison(config)


if __name__ == "__main__":
    main()
