#!/usr/bin/env python3
"""
Step 3: Generating embeddings with batching and checkpoints.

This script generates embeddings for all chunks with incremental saving
via checkpoints to allow resumption.

Usage:
    python setup_embeddings.py              # Generate/resume embeddings
    python setup_embeddings.py --reset      # Delete checkpoints and restart
    python setup_embeddings.py --batch-size 100  # Batch size
"""
import sys
import time
import argparse
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.embeddings import EmbeddingModel
from rag_pipeline.cli_utils import (
    print_header,
    CHECKPOINT_DIR,
    DEFAULT_BATCH_SIZE,
    get_checkpoint_path,
    count_existing_checkpoints,
    count_existing_embeddings,
    load_all_checkpoints,
    reset_checkpoints,
)


def run(config: Config, reset: bool = False, batch_size: int = DEFAULT_BATCH_SIZE) -> np.ndarray:
    """Entry point callable by the orchestrator.

    Args:
        config: Pipeline configuration
        reset: If True, deletes checkpoints and restarts
        batch_size: Batch size

    Returns:
        Numpy array of embeddings, or None in case of error
    """
    print_header("Generating embeddings (batched)", step="3/8")

    # Load chunks
    chunker = ConversationChunker(config)
    if not config.chunks_cache_path.exists():
        print("Error: No chunks found. Run setup_chunks.py first")
        return None

    chunks = chunker.load_chunks()
    print(f"{len(chunks)} chunks loaded")

    # Reset if requested
    if reset:
        reset_checkpoints(CHECKPOINT_DIR)

    # Create checkpoints directory
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    # Determine where to resume
    existing_checkpoints = count_existing_checkpoints(CHECKPOINT_DIR)
    start_idx = count_existing_embeddings(CHECKPOINT_DIR) if existing_checkpoints > 0 else 0

    if start_idx >= len(chunks):
        print(f"All embeddings are already generated ({existing_checkpoints} checkpoints)")
        embeddings = load_all_checkpoints(CHECKPOINT_DIR)
    else:
        if existing_checkpoints > 0:
            print(f"Resuming from checkpoint {existing_checkpoints}")
            print(f"   Existing embeddings: {start_idx}")
            print(f"   Remaining chunks: {len(chunks) - start_idx}")

        print()

        # Load embedding model
        embedding_model = EmbeddingModel(config)

        # Calculate remaining batches
        remaining_chunks = len(chunks) - start_idx
        n_batches = (remaining_chunks + batch_size - 1) // batch_size

        print(f"{n_batches} batch(es) to process")
        print()

        total_start_time = time.time()

        for batch_num in range(n_batches):
            batch_start = start_idx + (batch_num * batch_size)
            batch_end = min(batch_start + batch_size, len(chunks))
            batch_chunks = chunks[batch_start:batch_end]

            checkpoint_idx = existing_checkpoints + batch_num
            checkpoint_path = get_checkpoint_path(checkpoint_idx, CHECKPOINT_DIR)

            print(f"Batch {batch_num + 1}/{n_batches} (chunks {batch_start}-{batch_end})")

            # Prepare texts
            texts = [chunk.get_embedding_text() for chunk in batch_chunks]

            # Encode
            batch_start_time = time.time()
            batch_embeddings = embedding_model.encode(texts, show_progress=True)
            batch_time = time.time() - batch_start_time

            # Save checkpoint
            np.save(checkpoint_path, batch_embeddings)

            print(f"   Saved: {checkpoint_path.name}")
            print(f"   Time: {batch_time:.1f}s ({batch_time/len(batch_chunks):.2f}s/chunk)")
            print()

        total_time = time.time() - total_start_time
        print(f"Generation completed in {total_time:.1f}s")
        print()

        # Load all embeddings
        print("Loading all embeddings...")
        embeddings = load_all_checkpoints(CHECKPOINT_DIR)

    print(f"\nFinal shape: {embeddings.shape}")
    print(f"   - {embeddings.shape[0]} vectors")
    print(f"   - {embeddings.shape[1]} dimensions")
    print(f"   - {embeddings.nbytes / 1024 / 1024:.1f} MB")

    # Consistency check
    if len(embeddings) != len(chunks):
        print(f"WARNING: {len(embeddings)} embeddings != {len(chunks)} chunks")
        print("   Use --reset to restart cleanly")
        return None

    print()
    return embeddings


def main():
    parser = argparse.ArgumentParser(
        description="Step 3: Generating embeddings with batching and checkpoints"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Deletes checkpoints and restarts")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Batch size (default: {DEFAULT_BATCH_SIZE})")

    args = parser.parse_args()
    config = Config()

    embeddings = run(
        config,
        reset=args.reset,
        batch_size=args.batch_size
    )

    sys.exit(0 if embeddings is not None else 1)


if __name__ == "__main__":
    main()