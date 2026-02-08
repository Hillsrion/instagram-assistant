from rag_pipeline.core.models import Chunk
#!/usr/bin/env python3
"""
Create evaluation dataset filtered by complexity levels.

Creates a dataset of chunks classified as simple/medium/complex
using ChunkComplexityAnalyzer, suitable for eval_generation.py

Usage:
    python scripts/create_complexity_eval_dataset.py [--limit N]

Examples:
    python scripts/create_complexity_eval_dataset.py --limit 100
    python scripts/create_complexity_eval_dataset.py --limit 50
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.enrichment.complexity_analyzer import ChunkComplexityAnalyzer


def load_and_classify_chunks(limit: int = 100) -> dict:
    """Load chunks and classify by complexity."""
    chunks_path = Path(__file__).parent.parent / "rag_data" / "chunks.json"

    if not chunks_path.exists():
        print(f"❌ chunks.json not found at {chunks_path}")
        sys.exit(1)

    with open(chunks_path) as f:
        chunks_data = json.load(f)

    analyzer = ChunkComplexityAnalyzer()
    classified = defaultdict(list)

    print(f"Analyzing {min(limit, len(chunks_data))} chunks...")

    for i, chunk_data in enumerate(chunks_data[:limit]):
        if i % 50 == 0:
            print(f"  Progress: {i}/{min(limit, len(chunks_data))}")

        try:
            chunk = Chunk.from_dict(chunk_data)
            analysis = analyzer.analyze(chunk)

            classified[analysis.category].append({
                "chunk": chunk,
                "analysis": analysis,
                "chunk_data": chunk_data,
            })
        except Exception as e:
            print(f"⚠️  Could not load chunk: {e}")

    return classified


def create_eval_dataset(classified: dict, per_category: int = 10) -> dict:
    """Create eval dataset with balanced categories."""
    eval_dataset = defaultdict(list)

    print(f"\nCreating evaluation dataset...")
    print(f"  Target: {per_category} chunks per complexity level")

    for category in ["simple", "medium", "complex"]:
        chunks = classified[category][:per_category]
        print(f"  {category:8}: {len(chunks)} chunks")

        for item in chunks:
            chunk_data = item["chunk_data"]
            analysis = item["analysis"]

            eval_dataset[category].append({
                "chunk_id": chunk_data["chunk_id"],
                "conversation_id": chunk_data["conversation_id"],
                "content": chunk_data["content"],
                "message_count": chunk_data["message_count"],
                "participants": chunk_data["participants"],
                "complexity_score": analysis.score,
                "complexity_category": analysis.category,
            })

    return eval_dataset


def save_eval_dataset(eval_dataset: dict):
    """Save dataset for eval_generation.py."""
    output_path = Path(__file__).parent.parent / "eval" / "generation" / "complexity_eval_dataset.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to list format expected by eval framework
    dataset_list = []
    for category, chunks in eval_dataset.items():
        for chunk_data in chunks:
            dataset_list.append({
                "chunk_id": chunk_data["chunk_id"],
                "conversation_id": chunk_data["conversation_id"],
                "content": chunk_data["content"],
                "message_count": chunk_data["message_count"],
                "participants": chunk_data["participants"],
                "metadata": {
                    "complexity_score": chunk_data["complexity_score"],
                    "complexity_category": chunk_data["complexity_category"],
                }
            })

    with open(output_path, 'w') as f:
        json.dump(dataset_list, f, indent=2)

    print(f"\n✅ Dataset saved to {output_path}")
    print(f"   Total chunks: {len(dataset_list)}")
    print(f"   File size: {output_path.stat().st_size / 1024:.1f} KB")

    return output_path


def print_summary(classified: dict, eval_dataset: dict):
    """Print summary statistics."""
    print("\n" + "="*70)
    print("DATASET SUMMARY")
    print("="*70)

    print(f"\nChunks by complexity (from full dataset):")
    for category in ["simple", "medium", "complex"]:
        count = len(classified[category])
        print(f"  {category:8}: {count:3} chunks")

    total = sum(len(v) for v in eval_dataset.values())
    print(f"\nEvaluation dataset breakdown:")
    for category in ["simple", "medium", "complex"]:
        count = len(eval_dataset[category])
        print(f"  {category:8}: {count:3} chunks")

    print(f"\nTotal evaluation chunks: {total}")

    # Show sample chunks
    print(f"\nSample chunks:")
    for category in ["simple", "medium", "complex"]:
        if eval_dataset[category]:
            chunk = eval_dataset[category][0]
            print(f"\n  {category.upper()}:")
            print(f"    ID: {chunk['chunk_id']}")
            print(f"    Score: {chunk['complexity_score']:.3f}")
            print(f"    Messages: {chunk['message_count']}")
            print(f"    Participants: {len(chunk['participants'])}")
            print(f"    Preview: {chunk['content'][:80].replace(chr(10), ' ')}...")


def main():
    """Create evaluation dataset."""
    import argparse

    parser = argparse.ArgumentParser(description="Create complexity-based evaluation dataset")
    parser.add_argument("--limit", type=int, default=100,
                       help="Number of chunks to analyze (default: 100)")
    parser.add_argument("--per-category", type=int, default=10,
                       help="Chunks per complexity level (default: 10)")

    args = parser.parse_args()

    print("="*70)
    print("📊 CREATE COMPLEXITY EVALUATION DATASET")
    print("="*70)

    # Step 1: Load and classify
    classified = load_and_classify_chunks(args.limit)

    # Step 2: Create eval dataset
    eval_dataset = create_eval_dataset(classified, args.per_category)

    # Step 3: Save
    dataset_path = save_eval_dataset(eval_dataset)

    # Step 4: Summary
    print_summary(classified, eval_dataset)

    print("\n" + "="*70)
    print("✅ DATASET READY FOR EVALUATION")
    print("="*70)
    print(f"\nNext step: Run eval_generation.py")
    print(f"\nExample commands:")
    print(f"  # Compare 3B vs 8B on complexity-matched dataset")
    print(f"  python -m eval.generation.eval_generation ministral-3:3b ministral-3:8b")
    print(f"")
    print(f"  # With HTML report")
    print(f"  python -m eval.generation.eval_generation ministral-3:3b ministral-3:8b --html")
    print(f"\nResults will be in: eval/generation/results/")


if __name__ == "__main__":
    main()
