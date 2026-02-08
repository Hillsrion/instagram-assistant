#!/usr/bin/env python3
"""
Compare multiple RAG configurations on the evaluation dataset.

Usage:
    python -m eval.compare_configs
    python -m eval.compare_configs --question-type factual
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.core.config import Config

from eval.core import BenchmarkRunner
from eval.core._cli_utils import print_header, add_filter_arguments, parse_filters, load_qa_pairs


def run_comparison(config: Config, filters: dict = None):
    """Compare multiple configurations with optional filters."""
    print("Running configuration comparison...")
    print()

    # Load and filter QA pairs
    qa_pairs = load_qa_pairs(config, filters)
    if not qa_pairs:
        return

    print()

    # Run comparison
    runner = BenchmarkRunner(config)

    def progress(curr, total, msg):
        if curr == 0:
            print(f"\n{msg}")
        else:
            print(f"  [{curr}/{total}] {msg[:50]}", end="\r")

    reports = runner.compare_configs(qa_pairs, progress_callback=progress)

    print("\n")

    # Print comparison
    runner.print_comparison(reports)

    # Save
    runner.save_comparison(reports)


def main():
    parser = argparse.ArgumentParser(
        description="Compare multiple RAG configurations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m eval.compare_configs
    python -m eval.compare_configs --question-type factual,summary
    python -m eval.compare_configs --difficulty easy,medium
    python -m eval.compare_configs --participant "Alice"
        """
    )

    # Add filter arguments
    add_filter_arguments(parser)

    args = parser.parse_args()

    config = Config()

    print_header("RAG Evaluation - Configuration Comparison")

    filters = parse_filters(args)
    run_comparison(config, filters)


if __name__ == "__main__":
    main()
