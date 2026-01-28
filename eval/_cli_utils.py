"""
Shared CLI utilities for eval scripts.
"""

import argparse
from typing import List, Optional

from .synthetic_generator import SyntheticDataGenerator, QuestionFilter, QuestionType, Difficulty, QAPair
from rag_pipeline.config import Config


def print_header(title: str):
    """Print a standard header for CLI scripts."""
    print("=" * 60)
    print(title)
    print("=" * 60)
    print()


def add_filter_arguments(parser: argparse.ArgumentParser):
    """Add standard filter arguments to a parser."""
    parser.add_argument(
        '--question-type',
        type=str,
        metavar='TYPE[,TYPE...]',
        help=f'Filter by question type: {", ".join([t.value for t in QuestionType])}'
    )
    parser.add_argument(
        '--difficulty',
        type=str,
        metavar='LEVEL[,LEVEL...]',
        help=f'Filter by difficulty: {", ".join([d.value for d in Difficulty])}'
    )
    parser.add_argument(
        '--participant',
        type=str,
        metavar='NAME',
        help='Filter by participant name'
    )
    parser.add_argument(
        '--date-start',
        type=str,
        metavar='YYYY-MM-DD',
        help='Filter by date start (ISO format)'
    )
    parser.add_argument(
        '--date-end',
        type=str,
        metavar='YYYY-MM-DD',
        help='Filter by date end (ISO format)'
    )
    parser.add_argument(
        '--tags',
        type=str,
        metavar='TAG[,TAG...]',
        help='Filter by tags (comma-separated, must have all tags)'
    )


def parse_filters(args: argparse.Namespace) -> Optional[dict]:
    """
    Parse filter arguments into a dictionary for QuestionFilter.apply_filters().

    Returns None if no filters are specified.
    """
    filters = {}

    if hasattr(args, 'question_type') and args.question_type:
        filters['question_types'] = args.question_type.split(',')
    if hasattr(args, 'difficulty') and args.difficulty:
        filters['difficulties'] = args.difficulty.split(',')
    if hasattr(args, 'participant') and args.participant:
        filters['participant'] = args.participant
    if hasattr(args, 'date_start') and args.date_start and hasattr(args, 'date_end') and args.date_end:
        filters['start_date'] = args.date_start
        filters['end_date'] = args.date_end
    if hasattr(args, 'tags') and args.tags:
        filters['tags'] = args.tags.split(',')

    return filters if filters else None


def load_qa_pairs(config: Config, filters: Optional[dict] = None) -> Optional[List[QAPair]]:
    """
    Load QA pairs from the dataset and apply optional filters.

    Returns None if no dataset is found.
    Prints status messages about loading and filtering.
    """
    generator = SyntheticDataGenerator(config)
    qa_pairs = generator.load_dataset()

    if not qa_pairs:
        print("Error: No evaluation dataset found. Run: python -m eval.generate_dataset <n>")
        return None

    print(f"Loaded {len(qa_pairs)} QA pairs")

    if filters:
        original_count = len(qa_pairs)
        qa_pairs = QuestionFilter.apply_filters(qa_pairs, **filters)
        print(f"After filtering: {len(qa_pairs)} QA pairs")
        if not qa_pairs:
            print("Error: No QA pairs left after filtering.")
            return None
        if len(qa_pairs) < original_count:
            print(f"  (filtered out {original_count - len(qa_pairs)} pairs)")

    return qa_pairs
