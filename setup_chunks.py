#!/usr/bin/env python3
"""
Step 1: Loading and generating chunks.

This script loads Instagram conversations and splits them into chunks
for RAG processing.

Usage:
    python setup_chunks.py              # Load/generate chunks
    python setup_chunks.py --reset      # Regenerate chunks
    python setup_chunks.py --limit 10   # Limit to 10 conversations
    python setup_chunks.py --import-test  # Import test conversations
"""
import sys
import shutil
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.cli_utils import print_header


def run(config: Config, reset: bool = False, limit: int = None, import_test: bool = False, allowlist_file: Path = None) -> bool:
    """Entry point callable by the orchestrator.

    Args:
        config: Pipeline configuration
        reset: If True, regenerates chunks even if they exist
        limit: Limits the number of conversations to process
        import_test: Imports test conversations
        allowlist_file: Path to JSON file with allowed conversation IDs

    Returns:
        True if success, False otherwise
    """
    # Import test conversations if requested
    if import_test:
        test_dir = Path("test_conversations")
        target_dir = config.conversations_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        print_header("Importing test conversations")

        if test_dir.exists():
            count = 0
            for f in test_dir.glob("*.txt"):
                shutil.copy2(f, target_dir)
                print(f"   Copied: {f.name}")
                count += 1
            print(f"{count} conversations imported into {target_dir}")
        else:
            print(f"Test directory not found: {test_dir}")
        print()

    print_header("Loading chunks", step="1/8")

    chunker = ConversationChunker(config)

    # Check if chunks exist
    if config.chunks_cache_path.exists() and not reset:
        print(f"Loading from {config.chunks_cache_path}...")
        chunks = chunker.load_chunks()
        print(f"{len(chunks)} chunks loaded")
    else:
        if reset and config.chunks_cache_path.exists():
            print("Reset requested: regenerating chunks...")
        else:
            print("No cached chunks, generating...")

        def progress_callback(current, total, filename, num_chunks):
            if current % 100 == 0 or current == total:
                print(f"   [{current}/{total}] {filename} -> {num_chunks} chunks")

        # Load allowlist if provided
        allowlist = None
        if allowlist_file and allowlist_file.exists():
            import json
            try:
                with open(allowlist_file, 'r', encoding='utf-8') as f:
                    allowlist = set(json.load(f))
                print(f"   ℹ️  Allowlist loaded: {len(allowlist)} conversations")
            except Exception as e:
                print(f"   ⚠️  Error loading allowlist: {e}")

        chunks = chunker.chunk_all_conversations(
            progress_callback=progress_callback,
            limit=limit,
            allowlist=allowlist
        )
        chunker.save_chunks(chunks)
        print(f"{len(chunks)} chunks created and saved")

    print()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Step 1: Loading and generating chunks"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Regenerates chunks even if they exist")
    parser.add_argument("--limit", type=int,
                        help="Limits the number of conversations to process")
    parser.add_argument("--import-test", action="store_true",
                        help="Imports test conversations from test_conversations/")
    parser.add_argument("--allowlist-file", type=Path,
                        help="Path to a JSON file containing a list of conversation IDs to process")

    args = parser.parse_args()
    config = Config()

    success = run(
        config,
        reset=args.reset,
        limit=args.limit,
        import_test=args.import_test
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()