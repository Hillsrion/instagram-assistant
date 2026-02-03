#!/usr/bin/env python3
"""
Step 1: Loading and generating chunks.
"""
import sys
import shutil
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.cli_utils import print_header

def run(config: Config, reset: bool = False, limit: int = None, import_test: bool = False) -> bool:
    if import_test:
        test_dir = Path("test_conversations")
        target_dir = config.conversations_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        print_header("Importing test conversations")
        if test_dir.exists():
            for f in test_dir.glob("*.txt"):
                shutil.copy2(f, target_dir)
        print()

    print_header("Loading chunks", step="1/8")
    chunker = ConversationChunker(config)

    if config.chunks_cache_path.exists() and not reset:
        print(f"Loading from {config.chunks_cache_path}...")
        chunks = chunker.load_chunks()
        print(f"{len(chunks)} chunks loaded")
    else:
        print("Generating all chunks...")
        def progress_callback(current, total, filename, num_chunks):
            if current % 100 == 0 or current == total:
                print(f"   [{current}/{total}] {filename} -> {num_chunks} chunks")

        chunks = chunker.chunk_all_conversations(progress_callback=progress_callback, limit=limit)
        chunker.save_chunks(chunks)
        print(f"{len(chunks)} chunks created and saved")

    print()
    return True

def main():
    parser = argparse.ArgumentParser(description="Step 1: Loading and generating chunks")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--import-test", action="store_true")
    args = parser.parse_args()
    config = Config()
    success = run(config, reset=args.reset, limit=args.limit, import_test=args.import_test)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()