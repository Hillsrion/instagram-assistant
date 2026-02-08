"""
Generate multi-chunk QA dataset for evaluation.

This is a standalone script for generating the multi-chunk evaluation dataset.
It creates questions that genuinely require information from multiple chunks.

Usage:
    python -m eval.generate_multichunk_dataset
    python -m eval.generate_multichunk_dataset --size 50
    python -m eval.generate_multichunk_dataset --size 30 --chunks 5,10,15
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.core.config import Config
from rag_pipeline.indexing.chunker import ConversationChunker
from rag_pipeline.core.models import Chunk
from eval.synthetic_generator import SyntheticDataGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Generate multi-chunk QA evaluation dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script generates a dataset of questions that require reading
multiple conversation chunks to answer correctly.

The questions are categorized by intent:
  - specific_fact (5 chunks): Cross-reference questions
  - complex_reasoning (10 chunks): Multi-step reasoning
  - broad_summary (15 chunks): Comprehensive synthesis

Examples:
    python -m eval.generate_multichunk_dataset
    python -m eval.generate_multichunk_dataset --size 50
    python -m eval.generate_multichunk_dataset --size 30 --chunks 5,10,15
        """
    )
    parser.add_argument(
        "--size",
        type=int,
        default=30,
        help="Number of QA pairs to generate (default: 30)"
    )
    parser.add_argument(
        "--chunks",
        type=str,
        default="5,10,15",
        help="Comma-separated chunk counts to use (default: 5,10,15)"
    )
    args = parser.parse_args()

    chunk_counts = [int(x.strip()) for x in args.chunks.split(",")]

    print("=" * 70)
    print("Multi-Chunk Dataset Generation")
    print("=" * 70)
    print(f"Target size: {args.size} QA pairs")
    print(f"Chunk counts: {chunk_counts}")
    print()

    # Load configuration and chunks
    config = Config()
    chunker = ConversationChunker(config)
    print("Loading conversation chunks...")
    chunks = chunker.load_chunks()
    print(f"✓ Loaded {len(chunks)} chunks\n")

    # Create generator
    generator = SyntheticDataGenerator(config)

    # Progress callback
    def progress(current, total, message):
        print(f"[{current}/{total}] {message}")

    # Generate QA pairs
    print("Generating multi-chunk QA pairs...")
    print("(This may take several minutes as it uses LLM for generation)\n")

    qa_pairs = generator.generate_multichunk_qa_pairs(
        chunks,
        num_pairs=args.size,
        chunk_counts=chunk_counts,
        progress_callback=progress
    )

    # Save dataset
    print("\nSaving dataset...")
    generator.save_multichunk_dataset(qa_pairs)

    print(f"\n✅ Generated {len(qa_pairs)} multi-chunk QA pairs")

    # Display statistics
    print("\n" + "=" * 70)
    print("Dataset Statistics")
    print("=" * 70)

    by_intent = {}
    by_chunk_count = {}
    total_chunks = 0

    for qa in qa_pairs:
        by_intent[qa.intent] = by_intent.get(qa.intent, 0) + 1
        num_chunks = len(qa.source_chunk_ids)
        by_chunk_count[num_chunks] = by_chunk_count.get(num_chunks, 0) + 1
        total_chunks += num_chunks

    print(f"\nTotal QA pairs: {len(qa_pairs)}")
    print(f"Average chunks per question: {total_chunks / len(qa_pairs):.1f}")

    print("\nBy Intent:")
    for intent, count in sorted(by_intent.items()):
        print(f"  {intent:20s}: {count:3d} ({count/len(qa_pairs)*100:.1f}%)")

    print("\nBy Chunk Count:")
    for num_chunks, count in sorted(by_chunk_count.items()):
        print(f"  {num_chunks:2d} chunks: {count:3d} ({count/len(qa_pairs)*100:.1f}%)")

    # Show sample questions
    print("\n" + "=" * 70)
    print("Sample Questions")
    print("=" * 70)

    for intent in ["specific_fact", "complex_reasoning", "broad_summary"]:
        samples = [qa for qa in qa_pairs if qa.intent == intent]
        if samples:
            sample = samples[0]
            print(f"\n[{intent.upper()}] ({len(sample.source_chunk_ids)} chunks)")
            print(f"Q: {sample.question}")
            print(f"A: {sample.expected_answer[:150]}...")

    print("\n" + "=" * 70)
    print("Dataset saved to: eval/eval_dataset_multichunk.json")
    print("=" * 70)
    print("\nYou can now run evaluation with:")
    print("  python -m eval.eval_generation_multichunk qwen3:latest --trials 10")


if __name__ == "__main__":
    main()
