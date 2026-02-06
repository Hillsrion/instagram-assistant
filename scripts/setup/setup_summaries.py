#!/usr/bin/env python3
"""
Steps 7-8: Generating hierarchical summaries and their FAISS index.

This script generates conversation and period summaries via LLM,
then builds a dedicated FAISS index for searching these summaries.

Usage:
    python setup_summaries.py              # Generate summaries and their index
    python setup_summaries.py --reset      # Regenerate all summaries
    python setup_summaries.py --model qwen2.5:3b  # Override LLM model
"""
import sys
import time
import json
import argparse
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.embeddings import EmbeddingModel
from rag_pipeline.summary_generator import SummaryGenerator
from rag_pipeline.summary_store import SummaryStore
from rag_pipeline.summary_models import ConversationSummary, PeriodSummary
from rag_pipeline.cli_utils import print_header, format_duration


def run(config: Config, reset: bool = False, model: str = None) -> bool:
    """Entry point callable by the orchestrator.

    Args:
        config: Pipeline configuration
        reset: If True, regenerates all summaries
        model: Override LLM model

    Returns:
        True if success, False otherwise
    """
    if model:
        config.llm_model = model
        print(f"Override LLM model: {config.llm_model}")

    # Load chunks
    chunker = ConversationChunker(config)
    if not config.chunks_cache_path.exists():
        print("Error: No chunks found. Run setup_chunks.py first")
        return False

    chunks = chunker.load_chunks()
    print(f"{len(chunks)} chunks loaded")

    # Summary file paths
    conv_summaries_path = config.index_dir / "conversation_summaries.json"
    period_summaries_path = config.index_dir / "period_summaries.json"
    summary_index_path = config.index_dir / "summary_index"

    # Reset if requested
    if reset:
        import shutil
        if conv_summaries_path.exists():
            conv_summaries_path.unlink()
            print("Conversation summaries deleted")
        if period_summaries_path.exists():
            period_summaries_path.unlink()
            print("Period summaries deleted")
        if summary_index_path.exists():
            shutil.rmtree(summary_index_path)
            print("Summary index deleted")
        print()

    # ========================================
    # Step 7: Summary Generation
    # ========================================
    print_header("Generating Hierarchical Summaries (LLM)", step="7/8")

    conversation_summaries = []
    period_summaries = []

    if conv_summaries_path.exists() and period_summaries_path.exists() and not reset:
        print("Hierarchical summaries already generated.")
        with open(conv_summaries_path, 'r', encoding='utf-8') as f:
            conv_data = json.load(f)
        with open(period_summaries_path, 'r', encoding='utf-8') as f:
            period_data = json.load(f)
        print(f"   - {len(conv_data)} conversation summaries")
        print(f"   - {len(period_data)} period summaries")

        conversation_summaries = [ConversationSummary.from_dict(d) for d in conv_data]
        period_summaries = [PeriodSummary.from_dict(d) for d in period_data]
    else:
        print(f"Generating via Ollama ({config.llm_model})...")
        print("   This step may take time depending on the number of conversations.")

        summary_generator = SummaryGenerator(config)

        try:
            summary_start_time = time.time()

            def summary_progress(current, total, desc=""):
                elapsed = time.time() - summary_start_time
                speed = current / elapsed if elapsed > 0 else 0
                remaining = (total - current) / speed if speed > 0 else 0
                rem_str = format_duration(remaining)
                sys.stdout.write(f"\r   [{current}/{total}] {desc[:40]:<40} | Left: {rem_str}   ")
                sys.stdout.flush()

            def save_summaries(conv_sums, period_sums):
                with open(conv_summaries_path, 'w', encoding='utf-8') as f:
                    json.dump([s.to_dict() for s in conv_sums], f, ensure_ascii=False, indent=2)
                with open(period_summaries_path, 'w', encoding='utf-8') as f:
                    json.dump([s.to_dict() for s in period_sums], f, ensure_ascii=False, indent=2)

            conversation_summaries, period_summaries = summary_generator.generate_all_summaries(
                chunks,
                progress_callback=summary_progress,
                save_callback=save_summaries
            )

            print(f"\nSummaries generated: {len(conversation_summaries)} conversations, {len(period_summaries)} periods")

        except KeyboardInterrupt:
            print("\n\nInterruption: Partial summaries saved.")
            print("   Rerun script to resume.")
            return False

        except Exception as e:
            print(f"\n\nError during summary generation: {e}")
            return False

    print()

    # ========================================
    # Step 8: FAISS Index for Summaries
    # ========================================
    print_header("FAISS Index for Summaries", step="8/8")

    conv_index_exists = (summary_index_path / "conversation_index.faiss").exists()
    period_index_exists = (summary_index_path / "period_index.faiss").exists()

    if conv_index_exists and period_index_exists and not reset:
        print("Summary index already built.")
    else:
        if conversation_summaries or period_summaries:
            embedding_model = EmbeddingModel(config)
            summary_store = SummaryStore(config, embedding_model)
            summary_store.build_indexes(conversation_summaries, period_summaries)
            summary_store.save()
            print("Summary index built and saved.")
            
            # Print embedding metrics
            embedding_model.logger.export_csv()
            embedding_model.logger.print_summary()
        else:
            print("No summaries to index.")

    print()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Steps 7-8: Generating hierarchical summaries and their index"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Regenerate all summaries")
    parser.add_argument("--model", type=str,
                        help="Override LLM model (e.g. qwen2.5:3b)")

    args = parser.parse_args()
    config = Config()

    success = run(
        config,
        reset=args.reset,
        model=args.model
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()