#!/usr/bin/env python3
"""
Steps 4-6: Building indexes (FAISS, BM25, SQLite Metadata).

This script builds the various indexes needed for RAG:
- FAISS Index for vector search
- BM25 Index for lexical search
- SQLite Index for metadata filtering

Usage:
    python setup_indexes.py              # Builds all indexes
    python setup_indexes.py --reset      # Rebuilds all indexes
    python setup_indexes.py --only faiss # Builds only FAISS
    python setup_indexes.py --only bm25  # Builds only BM25
    python setup_indexes.py --only metadata  # Builds only metadata
"""
import sys
import argparse
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from rag_pipeline.core.config import Config
from rag_pipeline.indexing.chunker import ConversationChunker
from rag_pipeline.core.models import Chunk
from rag_pipeline.indexing.vector_store import VectorStore
from rag_pipeline.indexing.bm25_index import BM25Index
from rag_pipeline.indexing.metadata_store import MetadataStore
from rag_pipeline.utils.cli_utils import print_header, load_all_checkpoints, CHECKPOINT_DIR


def build_faiss_index(config: Config, chunks: list, embeddings) -> bool:
    """Builds the FAISS index."""
    print_header("Building FAISS Index", step="4/8")

    if embeddings is None:
        print("Error: No embeddings available.")
        return False

    vector_store = VectorStore(config)
    vector_store.build_index(chunks, embeddings)
    vector_store.save()
    print("FAISS Index built and saved")
    print()
    return True


def build_bm25_index(config: Config, chunks: list) -> bool:
    """Builds the BM25 index."""
    print_header("BM25 Index (lexical search)", step="5/8")

    bm25_index = BM25Index(config)
    bm25_index.chunks = chunks
    bm25_index.build_index(chunks)
    bm25_index.save()
    print("BM25 Index built and saved")
    print()
    return True


def build_metadata_index(config: Config, chunks: list) -> bool:
    """Builds the SQLite metadata index."""
    print_header("Metadata Index (SQLite)", step="6/8")

    metadata_store = MetadataStore(config)
    metadata_store.build_index(chunks)

    # Show some stats
    participants = metadata_store.get_all_participants()[:10]
    date_range = metadata_store.get_date_range()
    print(f"   - Period: {date_range[0][:10] if date_range[0] else 'N/A'} -> {date_range[1][:10] if date_range[1] else 'N/A'}")
    print(f"   - Top participants: {', '.join(p[0] for p in participants[:5])}")

    metadata_store.close()
    print("Metadata Index built and saved")
    print()
    return True


def run(config: Config, reset: bool = False, only: str = None) -> bool:
    """Entry point callable by the orchestrator.

    Args:
        config: Pipeline configuration
        reset: If True, rebuilds all indexes
        only: Builds only a specific index ('faiss', 'bm25', 'metadata')

    Returns:
        True if success, False otherwise
    """
    chunker = ConversationChunker(config)
    
    # Load chunks (from specialized indexed path if it exists, otherwise default)
    indexed_chunks_path = config.index_dir / "chunks_indexed.json"
    if indexed_chunks_path.exists():
        print(f"Loading specifically indexed chunks from {indexed_chunks_path}...")
        chunks = chunker.load_chunks(indexed_chunks_path)
    elif config.chunks_cache_path.exists():
        print(f"Loading from {config.chunks_cache_path}...")
        chunks = chunker.load_chunks()
    else:
        print("Error: No chunks found. Run setup_chunks.py first")
        return False

    print(f"{len(chunks)} chunks loaded for indexing")

    # Load embeddings if necessary
    embeddings = None
    if only is None or only == 'faiss':
        embeddings = load_all_checkpoints(CHECKPOINT_DIR, verbose=False)
        if embeddings is None:
            print("Error: No embeddings found. Run setup_embeddings.py first")
            if only == 'faiss':
                return False

    # Reset if requested
    if reset:
        import shutil
        if only is None or only == 'faiss':
            if config.vector_store_path.exists():
                shutil.rmtree(config.vector_store_path)
                print("FAISS Index deleted")
        if only is None or only == 'bm25':
            bm25_path = config.index_dir / "bm25_index.pkl"
            if bm25_path.exists():
                bm25_path.unlink()
                print("BM25 Index deleted")
        if only is None or only == 'metadata':
            metadata_path = config.index_dir / "metadata.db"
            if metadata_path.exists():
                metadata_path.unlink()
                print("Metadata Index deleted")
        print()

    success = True

    # Build requested indexes
    if only is None or only == 'faiss':
        if not build_faiss_index(config, chunks, embeddings):
            success = False

    if only is None or only == 'bm25':
        if not build_bm25_index(config, chunks):
            success = False

    if only is None or only == 'metadata':
        if not build_metadata_index(config, chunks):
            success = False

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Steps 4-6: Building indexes (FAISS, BM25, Metadata)"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Rebuilds all indexes")
    parser.add_argument("--only", choices=['faiss', 'bm25', 'metadata'],
                        help="Builds only a specific index")

    args = parser.parse_args()
    config = Config()

    success = run(
        config,
        reset=args.reset,
        only=args.only
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()