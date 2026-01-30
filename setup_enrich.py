#!/usr/bin/env python3
"""
Step 2: Semantic enrichment of chunks via LLM.

This script enriches chunks with narrative summaries and hypothetical questions
to improve RAG search quality.

Usage:
    python setup_enrich.py              # Enriches untreated chunks
    python setup_enrich.py --reset      # Re-enriches all chunks
    python setup_enrich.py --model qwen2.5:3b  # Override LLM model
"""
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.enricher import ChunkEnricher
from rag_pipeline.cli_utils import print_header, format_duration


def run(config: Config, reset: bool = False, model: str = None, total_shards: int = 1, shard_index: int = 0) -> bool:
    """Entry point callable by the orchestrator.

    Args:
        config: Pipeline configuration
        reset: If True, re-enriches all chunks
        model: Override LLM model
        total_shards: Total number of machines/processes
        shard_index: Index of this process (0 to total_shards-1)

    Returns:
        True if success, False otherwise
    """
    script_start_time = time.time()
    log_file = Path("enrichment.log")

    # Reset log if chunks file doesn't exist and log is not empty
    if not config.chunks_cache_path.exists() and log_file.exists() and log_file.stat().st_size > 0:
        try:
            with open(log_file, "w") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Log reset. Chunks file missing.\n")
            print("Enrichment log reset because chunks file is missing.")
        except Exception as e:
            print(f"Warning: Could not reset log file: {e}")

    if model:
        config.llm_model = model
        print(f"LLM Model Override: {config.llm_model}")

    print_header("Semantic Enrichment (LLM)", step="2/8")
    if total_shards > 1:
        print(f"Distributed Mode: Shard {shard_index + 1}/{total_shards}")

    # Load chunks
    chunker = ConversationChunker(config)
    if not config.chunks_cache_path.exists():
        print("Error: No chunks found. Run setup_chunks.py first")
        return False

    chunks = chunker.load_chunks()
    print(f"{len(chunks)} chunks loaded")

    # Determine which chunks to enrich
    if reset:
        to_enrich_all = chunks
        print(f"Reset requested: re-enriching all {len(chunks)} chunks")
        # Reset enrichment fields
        for c in to_enrich_all:
            c.narrative_summary = None
            c.hypothetical_questions = []
    else:
        to_enrich_all = [c for c in chunks if not c.narrative_summary or not c.hypothetical_questions]

    # Sharding application
    if total_shards > 1:
        to_enrich = [c for i, c in enumerate(to_enrich_all) if i % total_shards == shard_index]
        print(f"Shard {shard_index}: Processing {len(to_enrich)} chunks out of {len(to_enrich_all)} remaining")
    else:
        to_enrich = to_enrich_all

    if not to_enrich:
        print("All chunks assigned to this shard are already enriched.")
        print()
        return True

    print(f"Enriching {len(to_enrich)} chunks via Ollama ({config.llm_model})...")
    print("   This drastically improves search quality.")
    print("   (Auto-saving every 20 chunks)")

    enricher = ChunkEnricher(config)

    try:
        start_time = time.time()
        last_save_time = start_time

        def enrich_progress(current, total):
            if current % 5 == 0 or current == total:
                elapsed = time.time() - start_time
                speed = current / elapsed if elapsed > 0 else 0
                remaining = (total - current) / speed if speed > 0 else 0

                rem_str = format_duration(remaining)

                sys.stdout.write(f"\r   [{current}/{total}] chunks | Speed: {speed:.1f} ch/s | Left: {rem_str}   ")
                sys.stdout.flush()

        def save_progress():
            nonlocal last_save_time
            current_time = time.time()
            duration = current_time - last_save_time
            last_save_time = current_time

            # In shard mode, we save to the main file anyway
            # because we loaded all chunks into memory, we only modify ours.
            chunker.save_chunks(chunks)
            
            log_msg = f"Batch saved. Duration: {duration:.2f}s"
            sys.stdout.write(f"  {log_msg}\n")
            
            try:
                with open("enrichment.log", "a") as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {log_msg}\n")
            except Exception as e:
                sys.stdout.write(f"\nWarning: Could not write to log file: {e}\n")

        enricher.enrich_batch(
            to_enrich,
            progress_callback=enrich_progress,
            save_callback=save_progress,
            save_interval=20
        )

        chunker.save_chunks(chunks)
        print("\nChunks enriched and saved to cache.")

    except KeyboardInterrupt:
        print("\n\nInterruption: Saving already enriched chunks...")
        chunker.save_chunks(chunks)
        print("Save complete. Rerun script to resume.")
        return False

    except Exception as e:
        print(f"\n\nError during enrichment: {e}")
        print("   Attempting to save done work...")
        chunker.save_chunks(chunks)
        print("   Save complete.")
        return False

    total_duration = time.time() - script_start_time
    duration_str = format_duration(total_duration)
    msg = f"Enrichment finished in {duration_str}."
    print(msg)
    try:
        with open("enrichment.log", "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

    print()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Step 2: Semantic enrichment of chunks via LLM"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Re-enriches all chunks")
    parser.add_argument("--model", type=str,
                        help="Override LLM model (e.g. qwen2.5:3b)")
    parser.add_argument("--total-shards", type=int, default=1,
                        help="Total number of participating machines")
    parser.add_argument("--shard-index", type=int, default=0,
                        help="Index of this machine (0 to total-shards - 1)")

    args = parser.parse_args()
    config = Config()

    success = run(
        config,
        reset=args.reset,
        model=args.model,
        total_shards=args.total_shards,
        shard_index=args.shard_index
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()