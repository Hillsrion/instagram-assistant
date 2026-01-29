#!/usr/bin/env python3
"""
RAG Pipeline Orchestrator - Main Entry Point.

This script orchestrates the execution of all RAG pipeline steps:
1. Loading/Generating chunks (setup_chunks.py)
2. LLM Enrichment (setup_enrich.py)
3. Generating embeddings (setup_embeddings.py)
4-6. FAISS + BM25 + Metadata Indexes (setup_indexes.py)
7-8. Hierarchical Summaries + their index (setup_summaries.py)

Usage:
    python setup_rag.py                  # Runs the whole pipeline
    python setup_rag.py --status         # Shows status of all components
    python setup_rag.py --reset          # Full reset and restart
    python setup_rag.py --only chunks    # Runs a single step
    python setup_rag.py --skip-enrich    # Skips enrichment
    python setup_rag.py --limit 10       # Limits to 10 conversations
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.logger import initialize_logging
from rag_pipeline.cli_utils import (
    print_header,
    CHECKPOINT_DIR,
    DEFAULT_BATCH_SIZE,
    count_existing_checkpoints,
    load_all_checkpoints,
    reset_checkpoints,
)

# Import sub-scripts
import setup_chunks
import setup_enrich
import setup_embeddings
import setup_indexes
import setup_summaries


def show_status(config: Config):
    """Shows current indexing status."""
    print("=" * 60)
    print("STATUS - RAG Pipeline")
    print("=" * 60)

    # Chunks
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks() if config.chunks_cache_path.exists() else []
    print(f"\n[Chunks] {len(chunks)} (in {config.chunks_cache_path})")

    # Enrichment
    if chunks:
        enriched = sum(1 for c in chunks if c.narrative_summary and c.hypothetical_questions)
        print(f"[Enrichment] {enriched}/{len(chunks)} chunks enriched")

    # Checkpoints
    n_checkpoints = count_existing_checkpoints(CHECKPOINT_DIR)
    chunks_processed = n_checkpoints * DEFAULT_BATCH_SIZE
    print(f"\n[Embeddings]")
    print(f"   - Checkpoints: {n_checkpoints}")
    print(f"   - Chunks processed: ~{chunks_processed}")
    if chunks:
        print(f"   - Chunks remaining: ~{max(0, len(chunks) - chunks_processed)}")
        if n_checkpoints > 0:
            progress = min(100, (chunks_processed / len(chunks)) * 100)
            print(f"   - Progress: {progress:.1f}%")

    # FAISS Index
    faiss_path = config.vector_store_path / "index.faiss"
    if faiss_path.exists():
        print(f"\n[FAISS Index] Created ({faiss_path})")
    else:
        print(f"\n[FAISS Index] Not created")

    # BM25 Index
    bm25_path = config.index_dir / "bm25_index.pkl"
    if bm25_path.exists():
        print(f"[BM25 Index] Created ({bm25_path})")
    else:
        print(f"[BM25 Index] Not created")

    # Metadata Index
    metadata_path = config.index_dir / "metadata.db"
    if metadata_path.exists():
        print(f"[Metadata Index] Created ({metadata_path})")
    else:
        print(f"[Metadata Index] Not created")

    # Summaries
    conv_summaries_path = config.index_dir / "conversation_summaries.json"
    period_summaries_path = config.index_dir / "period_summaries.json"
    summary_index_path = config.index_dir / "summary_index"

    if conv_summaries_path.exists():
        import json
        with open(conv_summaries_path, 'r', encoding='utf-8') as f:
            conv_data = json.load(f)
        print(f"\n[Conversation Summaries] {len(conv_data)} summaries")
    else:
        print(f"\n[Conversation Summaries] Not generated")

    if period_summaries_path.exists():
        import json
        with open(period_summaries_path, 'r', encoding='utf-8') as f:
            period_data = json.load(f)
        print(f"[Period Summaries] {len(period_data)} summaries")
    else:
        print(f"[Period Summaries] Not generated")

    if (summary_index_path / "conversation_index.faiss").exists():
        print(f"[Summary Index] Created ({summary_index_path})")
    else:
        print(f"[Summary Index] Not created")

    print()


def full_reset(config: Config):
    """Full reset of all components."""
    import shutil

    print("Full RAG pipeline reset...")

    # Checkpoints
    reset_checkpoints(CHECKPOINT_DIR)

    # FAISS Index
    if config.vector_store_path.exists():
        shutil.rmtree(config.vector_store_path)
        print("FAISS Index deleted")

    # BM25
    bm25_path = config.index_dir / "bm25_index.pkl"
    if bm25_path.exists():
        bm25_path.unlink()
        print("BM25 Index deleted")

    # Metadata
    metadata_path = config.index_dir / "metadata.db"
    if metadata_path.exists():
        metadata_path.unlink()
        print("Metadata Index deleted")

    # Summaries
    conv_summaries_path = config.index_dir / "conversation_summaries.json"
    period_summaries_path = config.index_dir / "period_summaries.json"
    summary_index_path = config.index_dir / "summary_index"

    if conv_summaries_path.exists():
        conv_summaries_path.unlink()
        print("Conversation summaries deleted")
    if period_summaries_path.exists():
        period_summaries_path.unlink()
        print("Period summaries deleted")
    if summary_index_path.exists():
        shutil.rmtree(summary_index_path)
        print("Summary Index deleted")

    # Chunks (optional - kept by default)
    # if config.chunks_cache_path.exists():
    #     config.chunks_cache_path.unlink()
    #     print("Chunks cache deleted")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="RAG Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
    python setup_rag.py                  # Runs the whole pipeline
    python setup_rag.py --status         # Shows status
    python setup_rag.py --reset          # Full reset
    python setup_rag.py --only chunks    # Only chunks
    python setup_rag.py --skip-enrich --skip-summary  # Without enrichment or summaries
        """
    )

    # General options
    parser.add_argument("--status", action="store_true",
                        help="Shows status of all components")
    parser.add_argument("--reset", action="store_true",
                        help="Full reset and restart")

    # Selective execution
    parser.add_argument("--only", choices=['chunks', 'enrich', 'embed', 'indexes', 'summaries'],
                        help="Execute a single step")

    # Skip options
    parser.add_argument("--skip-enrich", action="store_true",
                        help="Skips LLM enrichment")
    parser.add_argument("--skip-embed", action="store_true",
                        help="Skips embedding generation")
    parser.add_argument("--skip-indexes", action="store_true",
                        help="Skips index creation")
    parser.add_argument("--skip-summary", action="store_true",
                        help="Skips hierarchical summaries")

    # Sub-script options
    parser.add_argument("--limit", type=int,
                        help="Limit number of conversations")
    parser.add_argument("--model", type=str,
                        help="Override LLM model (e.g. qwen2.5:3b)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Embedding batch size (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--import-test", action="store_true",
                        help="Import test conversations")
    parser.add_argument("--log-verbose", action="store_true",
                        help="Enable verbose logging")

    args = parser.parse_args()

    # Initialize logging according to flag
    initialize_logging(args.log_verbose)

    config = Config()

    if args.model:
        config.llm_model = args.model
        print(f"LLM Model Override: {config.llm_model}")

    # Status mode
    if args.status:
        show_status(config)
        return

    # Reset mode
    if args.reset:
        full_reset(config)

    # Display configuration
    print("=" * 60)
    print("RAG Pipeline - Indexing")
    print("=" * 60)
    print()
    if args.limit:
        print(f"Limit enabled: {args.limit} max conversations")
    print(f"Batch size: {args.batch_size}")
    print(f"Checkpoints: {CHECKPOINT_DIR}")
    print()

    # Selective execution
    if args.only:
        if args.only == 'chunks':
            setup_chunks.run(config, reset=args.reset, limit=args.limit, import_test=args.import_test)
        elif args.only == 'enrich':
            setup_enrich.run(config, reset=args.reset, model=args.model)
        elif args.only == 'embed':
            setup_embeddings.run(config, reset=args.reset, batch_size=args.batch_size)
        elif args.only == 'indexes':
            setup_indexes.run(config, reset=args.reset)
        elif args.only == 'summaries':
            setup_summaries.run(config, reset=args.reset, model=args.model)
        return

    # Full pipeline execution
    # Step 1: Chunks
    if not setup_chunks.run(config, reset=args.reset, limit=args.limit, import_test=args.import_test):
        print("Error at step 1 (chunks)")
        sys.exit(1)

    # Step 2: Enrichment
    if not args.skip_enrich:
        if not setup_enrich.run(config, reset=args.reset, model=args.model):
            print("Error at step 2 (enrichment)")
            # Continue anyway as enrichment is not critical
    else:
        print("Step 2/8: Enrichment skipped (--skip-enrich)")
        print()

    # Step 3: Embeddings
    embeddings = None
    if not args.skip_embed:
        embeddings = setup_embeddings.run(config, reset=args.reset, batch_size=args.batch_size)
        if embeddings is None:
            print("Error at step 3 (embeddings)")
            sys.exit(1)
    else:
        print("Step 3/8: Embeddings skipped (--skip-embed)")
        embeddings = load_all_checkpoints(CHECKPOINT_DIR, verbose=False)
        print()

    # Steps 4-6: Index
    if not args.skip_indexes:
        if not setup_indexes.run(config, reset=args.reset):
            print("Error at steps 4-6 (indexes)")
            sys.exit(1)
    else:
        print("Steps 4-6/8: Indexing skipped (--skip-indexes)")
        print()

    # Steps 7-8: Summaries
    if not args.skip_summary:
        if not setup_summaries.run(config, reset=args.reset, model=args.model):
            print("Error at steps 7-8 (summaries)")
            # Continue anyway
    else:
        print("Steps 7-8/8: Summaries skipped (--skip-summary)")
        print()

    # Final summary
    print("=" * 60)
    print("INDEXING COMPLETE - ADVANCED RAG")
    print("=" * 60)

    # Reload chunks for summary
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks() if config.chunks_cache_path.exists() else []

    print(f"Indexed chunks: {len(chunks)}")
    if embeddings is not None:
        print(f"Embeddings: {embeddings.shape}")
    else:
        print(f"Embeddings: (Not loaded)")
    print(f"FAISS Index: {config.vector_store_path}")
    print(f"BM25 Index: {config.index_dir / 'bm25_index.pkl'}")
    print(f"Metadata Index: {config.index_dir / 'metadata.db'}")
    print(f"Summary Index: {config.index_dir / 'summary_index'}")
    print()
    print("You can now launch the advanced chat with:")
    print("   python chat_instagram_advanced.py")
    print()
    print("   Or the simple chat with:")
    print("   python chat_instagram.py")
    print()


if __name__ == "__main__":
    main()