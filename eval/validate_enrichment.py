#!/usr/bin/env python3
"""
CLI script for validating chunk enrichment quality.

Usage:
    python validate_enrichment.py --chunks <count> --model <model> --output <format>
    python validate_enrichment.py --file <pickle> --report json
    python validate_enrichment.py --sample  # Validate last N chunks in index
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config, default_config
from rag_pipeline.chunker import Chunk, ConversationChunker
from rag_pipeline.enricher import ChunkEnricher
from eval_enrichment import (
    EnrichmentValidator,
    print_validation_report,
    print_benchmark_report,
)


def load_chunks_from_index(config: Config, limit: int = None) -> List[Chunk]:
    """Load chunks from the pickled chunk index."""
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks()
    if limit:
        chunks = chunks[:limit]
    return chunks


def validate_sample_chunks(
    config: Config,
    sample_size: int = 20,
    enrich: bool = False,
    model: str = "ministral-8b",
) -> None:
    """Validate a sample of chunks from the index."""
    print(f"[*] Loading {sample_size} chunks from index...")
    chunks = load_chunks_from_index(config, limit=sample_size)

    if not chunks:
        print("[!] No chunks found in index")
        return

    print(f"[+] Loaded {len(chunks)} chunks")

    if enrich:
        print(f"[*] Enriching chunks with {model}...")
        enricher = ChunkEnricher(config, provider="ollama")
        enricher.model = model
        enriched_count = 0

        for chunk in chunks:
            try:
                result = enricher.enrich_chunk(chunk)
                (
                    chunk.narrative_summary,
                    chunk.hypothetical_questions,
                    chunk.speaker_intents,
                    chunk.temporal_context,
                    chunk.entities,
                    chunk.emotions,
                    chunk.interaction_pattern,
                    chunk.initiative,
                    chunk.emotional_shift,
                    chunk.open_loops,
                ) = result
                enriched_count += 1
                print(f"  ✓ Enriched {enriched_count}/{len(chunks)}")
            except Exception as e:
                print(f"  [!] Error enriching chunk {chunk.chunk_id}: {e}")

    # Validate
    print(f"\n[*] Validating enrichment...")
    validator = EnrichmentValidator(config)
    report = validator.validate_chunks(chunks, verbose=True)

    # Print report
    print_benchmark_report(report)

    # Save JSON report
    output_file = Path("enrichment_validation_report.json")
    with open(output_file, "w") as f:
        json.dump(report.to_dict(), f, indent=2, default=str)
    print(f"\n[+] Report saved to {output_file}")


def validate_with_ground_truth(
    config: Config, ground_truth_file: str, sample_size: int = 20
) -> None:
    """
    Validate enrichment against manually annotated ground truth.

    Ground truth format (JSON):
    [
        {
            "chunk_id": "...",
            "expected_questions": ["Q1", "Q2"],
            "expected_entities": {"locations": [...], ...},
            "expected_emotion": "joy",
            ...
        }
    ]
    """
    print(f"[*] Loading ground truth from {ground_truth_file}...")
    with open(ground_truth_file, "r") as f:
        ground_truth = json.load(f)

    print(f"[+] Loaded {len(ground_truth)} ground truth annotations")

    chunks = load_chunks_from_index(config, limit=sample_size)
    validator = EnrichmentValidator(config)

    # Compare predictions vs ground truth
    matches = 0
    partial_matches = 0

    for gt in ground_truth[:len(chunks)]:
        chunk = next((c for c in chunks if c.chunk_id == gt["chunk_id"]), None)
        if not chunk:
            continue

        chunk_report = validator.validate_chunk(chunk)

        # Compare questions
        gt_questions = set(gt.get("expected_questions", []))
        pred_questions = set(chunk.hypothetical_questions or [])
        if gt_questions & pred_questions:
            partial_matches += 1

        # Print detailed comparison
        print(f"\n{chunk.chunk_id}:")
        print(f"  Ground truth questions: {gt_questions}")
        print(f"  Predicted questions: {pred_questions}")
        print(f"  Validation score: {chunk_report.overall_score:.2%}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate chunk enrichment quality"
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Validate a random sample of chunks from index",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=20,
        help="Number of chunks to validate (default: 20)",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Enrich chunks before validating (requires Ollama)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="ministral-8b",
        help="LLM model to use for enrichment (default: ministral-8b)",
    )
    parser.add_argument(
        "--ground-truth",
        type=str,
        help="Path to JSON file with ground truth annotations",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to config file",
    )

    args = parser.parse_args()

    # Load config
    config = default_config
    if args.config:
        config = Config.from_file(args.config)

    # Run validation
    if args.sample:
        validate_sample_chunks(
            config,
            sample_size=args.size,
            enrich=args.enrich,
            model=args.model,
        )
    elif args.ground_truth:
        validate_with_ground_truth(config, args.ground_truth, args.size)
    else:
        print("Usage: python validate_enrichment.py --sample [--enrich] [--size N]")
        print("       python validate_enrichment.py --ground-truth <file>")


if __name__ == "__main__":
    main()
