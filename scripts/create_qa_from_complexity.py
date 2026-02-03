#!/usr/bin/env python3
"""
Create QA dataset from complexity-filtered chunks.

Generates question-answer pairs from chunks classified by complexity level.
These QA pairs can be used with eval_generation.py to evaluate model quality.

Usage:
    python scripts/create_qa_from_complexity.py [--limit N]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.chunker import Chunk
from rag_pipeline.complexity_analyzer import ChunkComplexityAnalyzer


def create_qa_from_chunks():
    """Create QA pairs from complexity-filtered chunks."""
    # Load the complexity dataset
    dataset_path = Path(__file__).parent.parent / "eval" / "generation" / "complexity_eval_dataset.json"

    if not dataset_path.exists():
        print(f"❌ Dataset not found at {dataset_path}")
        print("   First run: python scripts/create_complexity_eval_dataset.py")
        sys.exit(1)

    with open(dataset_path) as f:
        chunks_data = json.load(f)

    print(f"Creating QA pairs from {len(chunks_data)} chunks...")

    qa_pairs = []

    for i, chunk_data in enumerate(chunks_data):
        chunk_id = chunk_data["chunk_id"]
        content = chunk_data["content"]
        metadata = chunk_data.get("metadata", {})
        category = metadata.get("complexity_category", "unknown")

        # Generate 1-2 questions per chunk based on complexity
        if category == "simple":
            # For simple chunks, ask basic factual questions
            questions = [
                "What is the main topic of this conversation?",
            ]
        elif category == "medium":
            # For medium chunks, ask about details and implications
            questions = [
                "What are the key points discussed in this conversation?",
                "What emotions or sentiments are present?",
            ]
        else:  # complex
            # For complex chunks, ask comprehensive questions
            questions = [
                "Summarize the main points and dynamics of this conversation",
                "What are the key relationships and interactions shown?",
                "What can you infer about the participants' intentions?",
            ]

        for question in questions:
            # Use the chunk's narrative summary as expected answer (if available)
            # Otherwise, use a simple summary based on content
            expected_answer = f"Based on {chunk_id}: {content[:100]}..."

            qa_pair = {
                "question": question,
                "expected_answer": expected_answer,
                "source_chunk_id": chunk_id,
                "source_chunk_ids": [chunk_id],
                "complexity_category": category,
                "complexity_score": metadata.get("complexity_score", 0),
            }
            qa_pairs.append(qa_pair)

            if len(qa_pairs) % 10 == 0:
                print(f"  Created {len(qa_pairs)} QA pairs...")

    # Save to eval/core/eval_dataset.json (expected by eval_generation.py)
    output_path = Path(__file__).parent.parent / "eval" / "core" / "eval_dataset.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(qa_pairs, f, indent=2)

    print(f"\n✅ Created {len(qa_pairs)} QA pairs")
    print(f"   Saved to: {output_path}")

    # Print summary by category
    by_category = {}
    for qa in qa_pairs:
        cat = qa.get("complexity_category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1

    print(f"\nBreakdown by complexity:")
    for cat in ["simple", "medium", "complex"]:
        count = by_category.get(cat, 0)
        print(f"  {cat:8}: {count} QA pairs")

    return output_path, qa_pairs


def main():
    """Generate QA dataset."""
    print("="*70)
    print("📊 CREATE QA DATASET FROM COMPLEXITY-FILTERED CHUNKS")
    print("="*70 + "\n")

    output_path, qa_pairs = create_qa_from_chunks()

    print("\n" + "="*70)
    print("✅ QA DATASET READY FOR EVALUATION")
    print("="*70)
    print(f"\nNext: Run eval_generation.py to compare model quality")
    print(f"\nExample commands:")
    print(f"  # Compare 3B vs 8B")
    print(f"  python -m eval.generation.eval_generation ministral-3:3b ministral-3:8b")
    print(f"\n  # With HTML report")
    print(f"  python -m eval.generation.eval_generation ministral-3:3b ministral-3:8b --html")
    print(f"\nResults will be saved to: eval/generation/results/")


if __name__ == "__main__":
    main()
