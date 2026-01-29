#!/usr/bin/env python3
"""
Incremental Index Update Script.

Detects changes in conversation files and updates the index incrementally:
- New files: chunk, enrich, embed, add to index
- Modified files: remove old chunks, re-process, update index
- Deleted files: remove chunks from index

Usage:
    python update_index.py           # Run incremental update
    python update_index.py --full    # Force full rebuild
    python update_index.py --status  # Show status only
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.embeddings import EmbeddingModel
from rag_pipeline.vector_store import VectorStore
from rag_pipeline.bm25_index import BM25Index
from rag_pipeline.metadata_store import MetadataStore
from rag_pipeline.delta_tracker import DeltaTracker


def show_status(config: Config):
    """Show current index status and pending changes."""
    print("=" * 60)
    print("Index Status")
    print("=" * 60)
    print()

    # Load tracker
    tracker = DeltaTracker(config)
    stats = tracker.get_stats()

    print(f"Tracked files: {stats['tracked_files']}")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Total size: {stats['total_size_mb']} MB")
    print()

    # Detect changes
    delta = tracker.detect_changes()

    print("Pending changes:")
    print(f"  New files: {len(delta.new_files)}")
    for f in delta.new_files[:5]:
        print(f"    + {f.name}")
    if len(delta.new_files) > 5:
        print(f"    ... and {len(delta.new_files) - 5} more")

    print(f"  Modified files: {len(delta.modified_files)}")
    for f in delta.modified_files[:5]:
        print(f"    ~ {f.name}")
    if len(delta.modified_files) > 5:
        print(f"    ... and {len(delta.modified_files) - 5} more")

    print(f"  Deleted files: {len(delta.deleted_files)}")
    for f in delta.deleted_files[:5]:
        print(f"    - {Path(f).name}")
    if len(delta.deleted_files) > 5:
        print(f"    ... and {len(delta.deleted_files) - 5} more")

    print()
    if delta.has_changes:
        print("Run 'python update_index.py' to apply changes.")
    else:
        print("Index is up to date.")


def run_incremental_update(config: Config, force_full: bool = False):
    """Run incremental index update."""
    print("=" * 60)
    print("Incremental Index Update")
    print("=" * 60)
    print()

    tracker = DeltaTracker(config)

    # Detect changes
    delta = tracker.detect_changes()
    print(f"Changes detected: {delta.summary()}")

    if not delta.has_changes and not force_full:
        print("No changes detected. Index is up to date.")
        return

    if force_full:
        print("Full rebuild requested.")
        delta.new_files = list(config.conversations_dir.glob('*.txt'))
        delta.modified_files = []
        delta.deleted_files = list(tracker.file_states.keys())

    # Load components
    print("\nLoading components...")
    chunker = ConversationChunker(config)
    embedding_model = EmbeddingModel(config)
    vector_store = VectorStore(config)

    # Load existing index if not full rebuild
    if not force_full and (config.vector_store_path / "index.faiss").exists():
        vector_store.load()

    # Collect chunk IDs to remove (from modified and deleted files)
    files_to_remove = [str(f) for f in delta.modified_files] + delta.deleted_files
    chunk_ids_to_remove = tracker.get_all_chunk_ids_for_files(files_to_remove)

    if chunk_ids_to_remove:
        print(f"\nRemoving {len(chunk_ids_to_remove)} old chunks...")

    # Process new and modified files
    files_to_process = delta.new_files + delta.modified_files
    new_chunks = []

    if files_to_process:
        print(f"\nProcessing {len(files_to_process)} files...")

        for i, file_path in enumerate(files_to_process):
            print(f"  [{i+1}/{len(files_to_process)}] {file_path.name}")

            try:
                file_chunks = chunker.chunk_conversation(file_path)
                new_chunks.extend(file_chunks)

                # Update tracker state
                chunk_ids = [c.chunk_id for c in file_chunks]
                tracker.update_file_state(file_path, chunk_ids)

            except Exception as e:
                print(f"    Error: {e}")
                continue

    # Remove deleted file states
    for deleted_path in delta.deleted_files:
        tracker.remove_file_state(deleted_path)

    # Enrich new chunks (optional - check if enricher is available)
    try:
        from rag_pipeline.enricher import ChunkEnricher

        if new_chunks:
            print(f"\nEnriching {len(new_chunks)} chunks...")
            enricher = ChunkEnricher(config)

            # Check for existing enrichment state
            enrichment_state_path = config.index_dir / "enrichment_state.json"
            if enrichment_state_path.exists():
                enricher.load_state(enrichment_state_path)

            # Enrich only new chunks
            new_chunks = enricher.enrich_chunks(
                new_chunks,
                progress_callback=lambda curr, total, _: print(f"  [{curr}/{total}]", end="\r")
            )
            print()

            # Save enrichment state
            enricher.save_state(enrichment_state_path)

    except ImportError:
        print("Enricher not available, skipping enrichment.")

    # Generate embeddings for new chunks
    if new_chunks:
        print(f"\nGenerating embeddings for {len(new_chunks)} chunks...")
        texts = [chunk.get_embedding_text() for chunk in new_chunks]
        new_embeddings = embedding_model.encode_batch(
            texts,
            show_progress=True
        )

        # Update vector store
        if chunk_ids_to_remove and vector_store.index is not None:
            removed, added = vector_store.update_vectors(
                list(chunk_ids_to_remove),
                new_chunks,
                new_embeddings
            )
        else:
            vector_store.add_vectors(new_chunks, new_embeddings)

        # Save vector store
        print("\nSaving vector store...")
        vector_store.save()
    elif chunk_ids_to_remove and vector_store.index is not None:
        # Only removals, no new chunks
        vector_store.remove_vectors(list(chunk_ids_to_remove))
        vector_store.save()

    # Rebuild BM25 index (fast, always full rebuild)
    print("\nRebuilding BM25 index...")
    bm25_index = BM25Index(config)
    bm25_index.build_index(vector_store.chunks)
    bm25_index.save()

    # Rebuild metadata index (fast, always full rebuild)
    print("Rebuilding metadata index...")
    metadata_store = MetadataStore(config)
    metadata_store.build_index(vector_store.chunks)
    metadata_store.close()

    # Save tracker state
    print("\nSaving tracker state...")
    tracker.save_state()

    # Summary
    print("\n" + "=" * 60)
    print("Update Complete")
    print("=" * 60)
    print(f"Total chunks in index: {vector_store.size}")
    print(f"Tracked files: {len(tracker.file_states)}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Incremental Index Update",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--full',
        action='store_true',
        help='Force full index rebuild'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show status only, no updates'
    )

    args = parser.parse_args()

    config = Config()

    if args.status:
        show_status(config)
    else:
        run_incremental_update(config, force_full=args.full)


if __name__ == "__main__":
    main()