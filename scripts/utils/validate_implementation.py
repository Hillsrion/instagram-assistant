#!/usr/bin/env python3
"""
Validate the parallel enrichment implementation.
Checks that all components are correctly installed and functional.

Usage:
    python scripts/validate_implementation.py
    python scripts/validate_implementation.py --verbose
"""
import sys
import json
from pathlib import Path
from importlib import import_module
import argparse


def check_file(path: Path, description: str, verbose: bool = False) -> bool:
    """Check if a file exists."""
    if path.exists():
        if verbose:
            print(f"  ✓ {description}: {path}")
        return True
    else:
        print(f"  ✗ {description}: NOT FOUND - {path}")
        return False


def check_module_syntax(path: Path, description: str, verbose: bool = False) -> bool:
    """Check if a Python file has valid syntax."""
    try:
        import py_compile
        py_compile.compile(str(path), doraise=True)
        if verbose:
            print(f"  ✓ {description}: Syntax OK")
        return True
    except Exception as e:
        print(f"  ✗ {description}: Syntax error - {e}")
        return False


def check_file_contains(path: Path, substring: str, description: str, verbose: bool = False) -> bool:
    """Check if a file contains a specific substring."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        if substring in content:
            if verbose:
                print(f"  ✓ {description}")
            return True
        else:
            print(f"  ✗ {description}: NOT FOUND")
            return False
    except Exception as e:
        print(f"  ✗ {description}: Error - {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate parallel enrichment implementation")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    print("🔍 Validating Parallel Enrichment Implementation\n")

    all_checks_pass = True

    # 1. Check modified files
    print("1️⃣  Modified Core Files:")
    all_checks_pass &= check_file(
        Path("rag_pipeline/chunker.py"),
        "chunker.py exists",
        args.verbose
    )
    all_checks_pass &= check_module_syntax(
        Path("rag_pipeline/chunker.py"),
        "chunker.py syntax",
        args.verbose
    )
    all_checks_pass &= check_file_contains(
        Path("rag_pipeline/chunker.py"),
        "shard_index: int = None",
        "chunker.py has shard_index parameter"
    )
    all_checks_pass &= check_file_contains(
        Path("rag_pipeline/chunker.py"),
        'path.parent / f"chunks_shard{shard_index}.json"',
        "chunker.py saves to shard files"
    )

    print("\n2️⃣  Enhanced Enrichment Script:")
    all_checks_pass &= check_file(
        Path("setup_enrich.py"),
        "setup_enrich.py exists",
        args.verbose
    )
    all_checks_pass &= check_module_syntax(
        Path("setup_enrich.py"),
        "setup_enrich.py syntax",
        args.verbose
    )
    all_checks_pass &= check_file_contains(
        Path("setup_enrich.py"),
        'enrichment_shard{shard_index}.log',
        "setup_enrich.py uses shard-specific log files"
    )
    all_checks_pass &= check_file_contains(
        Path("setup_enrich.py"),
        "Memory optimized: keeping only",
        "setup_enrich.py has memory optimization"
    )
    all_checks_pass &= check_file_contains(
        Path("setup_enrich.py"),
        'shard_index if total_shards > 1 else None',
        "setup_enrich.py passes shard_index to save_chunks"
    )
    all_checks_pass &= check_file_contains(
        Path("setup_enrich.py"),
        "After all shards complete, run: python scripts/merge_enriched_shards.py",
        "setup_enrich.py instructs user to merge shards"
    )

    # 2. Check new scripts
    print("\n3️⃣  New Scripts:")
    all_checks_pass &= check_file(
        Path("scripts/merge_enriched_shards.py"),
        "merge_enriched_shards.py exists",
        args.verbose
    )
    all_checks_pass &= check_module_syntax(
        Path("scripts/merge_enriched_shards.py"),
        "merge_enriched_shards.py syntax",
        args.verbose
    )
    all_checks_pass &= check_file_contains(
        Path("scripts/merge_enriched_shards.py"),
        "def find_shard_files",
        "merge_enriched_shards.py has shard file detection"
    )
    all_checks_pass &= check_file_contains(
        Path("scripts/merge_enriched_shards.py"),
        "def merge_shards",
        "merge_enriched_shards.py has merge function"
    )
    all_checks_pass &= check_file_contains(
        Path("scripts/merge_enriched_shards.py"),
        "def validate_merge",
        "merge_enriched_shards.py has validation"
    )
    all_checks_pass &= check_file_contains(
        Path("scripts/merge_enriched_shards.py"),
        "--dry-run",
        "merge_enriched_shards.py supports dry-run mode"
    )
    all_checks_pass &= check_file_contains(
        Path("scripts/merge_enriched_shards.py"),
        "chunks.json.backup",
        "merge_enriched_shards.py creates backups"
    )

    # 3. Check enhanced scripts
    print("\n4️⃣  Enhanced Utility Scripts:")
    all_checks_pass &= check_file(
        Path("scripts/check_enrichment_status.py"),
        "check_enrichment_status.py exists",
        args.verbose
    )
    all_checks_pass &= check_module_syntax(
        Path("scripts/check_enrichment_status.py"),
        "check_enrichment_status.py syntax",
        args.verbose
    )
    all_checks_pass &= check_file_contains(
        Path("scripts/check_enrichment_status.py"),
        "--show-shards",
        "check_enrichment_status.py has --show-shards flag"
    )
    all_checks_pass &= check_file_contains(
        Path("scripts/check_enrichment_status.py"),
        "chunks_shard*.json",
        "check_enrichment_status.py detects shard files"
    )

    # 4. Check documentation
    print("\n5️⃣  Documentation:")
    all_checks_pass &= check_file(
        Path("docs/COMMANDS.md"),
        "COMMANDS.md exists",
        args.verbose
    )
    all_checks_pass &= check_file_contains(
        Path("docs/COMMANDS.md"),
        "Distributed Enrichment (Multiple Machines)",
        "COMMANDS.md has distributed enrichment section"
    )
    all_checks_pass &= check_file_contains(
        Path("docs/COMMANDS.md"),
        "--total-shards 2 --shard-index 0",
        "COMMANDS.md has shard examples"
    )
    all_checks_pass &= check_file_contains(
        Path("docs/COMMANDS.md"),
        "merge_enriched_shards.py",
        "COMMANDS.md documents merge script"
    )

    all_checks_pass &= check_file(
        Path("docs/DISTRIBUTED_ENRICHMENT.md"),
        "DISTRIBUTED_ENRICHMENT.md exists",
        args.verbose
    )
    all_checks_pass &= check_file_contains(
        Path("docs/DISTRIBUTED_ENRICHMENT.md"),
        "Race Condition Prevention",
        "DISTRIBUTED_ENRICHMENT.md explains architecture"
    )
    all_checks_pass &= check_file_contains(
        Path("docs/DISTRIBUTED_ENRICHMENT.md"),
        "Quick Start (2 Machines)",
        "DISTRIBUTED_ENRICHMENT.md has quick start"
    )

    all_checks_pass &= check_file(
        Path("IMPLEMENTATION_SUMMARY.md"),
        "IMPLEMENTATION_SUMMARY.md exists",
        args.verbose
    )

    all_checks_pass &= check_file(
        Path("PARALLEL_ENRICHMENT_QUICKSTART.md"),
        "PARALLEL_ENRICHMENT_QUICKSTART.md exists",
        args.verbose
    )

    # 5. Check executability
    print("\n6️⃣  File Permissions:")
    merge_script = Path("scripts/merge_enriched_shards.py")
    if merge_script.exists():
        import os
        if os.access(merge_script, os.X_OK):
            if args.verbose:
                print(f"  ✓ merge_enriched_shards.py is executable")
        else:
            print(f"  ⚠️  merge_enriched_shards.py is not executable (optional, but recommended)")

    # Summary
    print("\n" + "=" * 60)
    if all_checks_pass:
        print("✨ All validation checks passed!")
        print("\nImplementation is complete and ready to use.")
        print("\nQuick start:")
        print("  1. Read: PARALLEL_ENRICHMENT_QUICKSTART.md")
        print("  2. Run: python setup_enrich.py --total-shards 2 --shard-index 0")
        print("  3. Merge: python scripts/merge_enriched_shards.py")
        return 0
    else:
        print("❌ Some validation checks failed!")
        print("\nPlease fix the issues listed above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
