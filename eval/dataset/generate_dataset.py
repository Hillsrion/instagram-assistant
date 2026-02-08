#!/usr/bin/env python3
"""
Generate synthetic QA dataset for RAG evaluation.

Usage:
    python -m eval.generate_dataset 50
    python -m eval.generate_dataset --samples 50
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.core.config import Config
from rag_pipeline.indexing.chunker import ConversationChunker
from rag_pipeline.core.models import Chunk

from eval.core import SyntheticDataGenerator
from eval.core._cli_utils import print_header


def generate_dataset(n_samples: int, config: Config):
    """Generate synthetic QA dataset."""
    print(f"Generating {n_samples} QA pairs...")
    print()

    # Load ALL chunks from chunker (not VectorStore which may have limited index)
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks()
    if not chunks:
        print("Error: No chunks found. Run setup_rag_batch.py first.")
        return
    print(f"Loaded {len(chunks)} chunks from cache")

    # Generate
    generator = SyntheticDataGenerator(config)

    def progress(curr, total, msg):
        print(f"  [{curr}/{total}] {msg}")

    qa_pairs = generator.generate_dataset(
        chunks,
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


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic QA dataset for RAG evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m eval.generate_dataset 50
    python -m eval.generate_dataset --samples 50
        """
    )

    parser.add_argument(
        'n_samples',
        type=int,
        nargs='?',
        help='Number of QA pairs to generate'
    )
    parser.add_argument(
        '--samples',
        type=int,
        metavar='N',
        help='Number of QA pairs to generate (alternative to positional arg)'
    )

    args = parser.parse_args()

    # Get number of samples from either positional or --samples argument
    n_samples = args.n_samples or args.samples

    if not n_samples:
        parser.print_help()
        print("\nError: Must specify number of samples to generate")
        return

    config = Config()

    print_header("RAG Evaluation - Dataset Generation")

    generate_dataset(n_samples, config)


if __name__ == "__main__":
    main()
