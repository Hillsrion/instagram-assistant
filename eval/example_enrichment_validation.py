"""
Example: How to use the EnrichmentValidator to validate enriched chunks.

This example shows:
1. Creating sample enriched chunks
2. Validating them individually
3. Running a benchmark across multiple chunks
4. Analyzing results and identifying issues
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.chunker import Chunk
from rag_pipeline.config import default_config
from eval_enrichment import EnrichmentValidator, print_validation_report, print_benchmark_report


def example_1_validate_single_chunk():
    """Example 1: Validate a single enriched chunk."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Validating a Single Enriched Chunk")
    print("="*70)

    # Create a sample enriched chunk
    chunk = Chunk(
        chunk_id="chunk_001",
        conversation_id="conv_alice_bob",
        participants=["Alice", "Bob"],
        date_start="2024-01-15",
        date_end="2024-01-15",
        message_count=8,
        content="Alice: Hey Bob! Did you see the new restaurant on Main St?\nBob: No, where is it?\n...",
        file_source="conversations/alice_bob.txt",
        # Enrichment fields
        narrative_summary="Alice recommends a new restaurant to Bob",
        hypothetical_questions=[
            "What new restaurant did Alice mention?",
            "Where is the restaurant located?",
            "Was Bob interested in trying it?"
        ],
        speaker_intents={
            "Alice": "Share discovery about new restaurant",
            "Bob": "Learn about the restaurant location and details"
        },
        temporal_context="January 2024, weekday afternoon",
        entities={
            "locations": ["Main St", "Restaurant"],
            "people": [],
            "media": [],
            "events": []
        },
        emotions={
            "dominant": "enthusiasm",
            "tone": "casual and friendly",
            "tension_level": "low"
        },
        interaction_pattern="Information sharing",
        initiative="Alice leads with suggestion",
        emotional_shift="Stable",
        open_loops=["Whether Bob will visit the restaurant"]
    )

    # Validate the chunk
    validator = EnrichmentValidator(default_config)
    report = validator.validate_chunk(chunk)

    # Print the report
    print_validation_report(report)


def example_2_validate_multiple_chunks():
    """Example 2: Validate multiple chunks and get aggregated metrics."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Validating Multiple Chunks (Benchmark)")
    print("="*70)

    # Create sample enriched chunks
    chunks = [
        Chunk(
            chunk_id="chunk_001",
            conversation_id="conv_001",
            participants=["User1", "User2"],
            date_start="2024-01-15",
            date_end="2024-01-15",
            message_count=5,
            content="Discussion about weekend plans",
            file_source="test.txt",
            narrative_summary="Users discuss weekend plans",
            hypothetical_questions=["What are the weekend plans?"],
            speaker_intents={"User1": "Propose plan", "User2": "Discuss options"},
            temporal_context="Friday evening",
            entities={"locations": [], "people": [], "media": [], "events": []},
            emotions={"dominant": "excitement", "tone": "casual", "tension_level": "low"},
            interaction_pattern="Planning",
            initiative="User1",
            emotional_shift="Stable",
            open_loops=[]
        ),
        Chunk(
            chunk_id="chunk_002",
            conversation_id="conv_001",
            participants=["User1", "User2"],
            date_start="2024-01-16",
            date_end="2024-01-16",
            message_count=3,
            content="Quick message exchange",
            file_source="test.txt",
            narrative_summary="",  # Empty summary
            hypothetical_questions=[],  # No questions
            speaker_intents={},  # Empty intents
            temporal_context="",
            entities={},  # Empty entities
            emotions={},
            interaction_pattern=None,
            initiative=None,
            emotional_shift="Stable",
            open_loops=None
        ),
        Chunk(
            chunk_id="chunk_003",
            conversation_id="conv_002",
            participants=["Alice", "Charlie"],
            date_start="2024-01-20",
            date_end="2024-01-20",
            message_count=12,
            content="Long conversation about movie night",
            file_source="test.txt",
            narrative_summary="Alice and Charlie plan to watch a movie together",
            hypothetical_questions=[
                "What movie are they planning to watch?",
                "When will they watch it?",
                "Where will they meet?"
            ],
            speaker_intents={
                "Alice": "Organize movie night",
                "Charlie": "Confirm availability and movie choice"
            },
            temporal_context="Evening of January 20th",
            entities={
                "locations": ["Alice's apartment"],
                "people": [],
                "media": ["Movie"],
                "events": ["Movie night"]
            },
            emotions={"dominant": "joy", "tone": "playful", "tension_level": "low"},
            interaction_pattern="Planning",
            initiative="Balanced",
            emotional_shift="Neutral → Excited",
            open_loops=["Final movie choice to confirm"]
        ),
    ]

    # Run validation benchmark
    validator = EnrichmentValidator(default_config)
    report = validator.validate_chunks(chunks, verbose=True)

    # Print aggregate report
    print_benchmark_report(report)

    # Print per-chunk details
    print("\n" + "="*70)
    print("DETAILED CHUNK REPORTS")
    print("="*70)
    for chunk_report in report.chunk_reports:
        print_validation_report(chunk_report)


def example_3_identify_patterns():
    """Example 3: Analyze validation results to identify patterns."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Identifying Common Enrichment Issues")
    print("="*70)

    # Create chunks with intentional issues
    problematic_chunks = [
        Chunk(
            chunk_id="issue_001",
            conversation_id="conv_001",
            participants=["User1", "User2"],
            date_start="2024-01-15",
            date_end="2024-01-15",
            message_count=5,
            content="Message content",
            file_source="test.txt",
            narrative_summary="",  # ISSUE: Empty summary
            hypothetical_questions=["Q"],  # ISSUE: Too short
            speaker_intents={},  # ISSUE: Empty
            temporal_context="",
            entities=None,  # ISSUE: None instead of dict
            emotions={"dominant": "happy", "tone": "serious", "tension_level": "invalid"},  # ISSUE: Invalid tension
            interaction_pattern="Unknown pattern",  # ISSUE: Invalid pattern
            initiative="Non-existent person",  # ISSUE: Not a participant
            emotional_shift="No arrow format",  # ISSUE: Wrong format
            open_loops=["Topic 1", "Topic 2", "Topic 3", "Topic 4", "Topic 5"]  # Many loops
        ),
    ]

    validator = EnrichmentValidator(default_config)
    report = validator.validate_chunks(problematic_chunks, verbose=True)

    # Analyze issues
    print("\n" + "="*70)
    print("ISSUE ANALYSIS")
    print("="*70)
    for chunk_report in report.chunk_reports:
        print(f"\nChunk: {chunk_report.chunk_id}")
        print(f"Overall Score: {chunk_report.overall_score:.2%}")
        print(f"Critical Issues: {chunk_report.critical_issues}")

        for field_name, field_result in chunk_report.field_results.items():
            if field_result.issues or field_result.warnings:
                print(f"\n  {field_name.upper()}:")
                for issue in field_result.issues:
                    print(f"    ❌ {issue}")
                for warning in field_result.warnings:
                    print(f"    ⚠️  {warning}")


def example_4_field_by_field_analysis():
    """Example 4: Detailed field-by-field analysis."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Field-by-Field Analysis")
    print("="*70)

    chunk = Chunk(
        chunk_id="analysis_chunk",
        conversation_id="conv_001",
        participants=["Person A", "Person B"],
        date_start="2024-01-15",
        date_end="2024-01-15",
        message_count=10,
        content="Sample conversation",
        file_source="test.txt",
        narrative_summary="This is a good summary with appropriate length for a one-sentence summary",
        hypothetical_questions=[
            "What was discussed?",
            "Who participated?",
            "What decision was made?"
        ],
        speaker_intents={
            "Person A": "Propose solution",
            "Person B": "Evaluate proposal and provide feedback",
            "Extra Person": "This person wasn't in the conversation"
        },
        temporal_context="Tuesday afternoon in early January",
        entities={
            "locations": ["Office", "Coffee shop"],
            "people": ["John", "Sarah"],
            "media": [],
            "events": ["Team meeting"]
        },
        emotions={
            "dominant": "professional",
            "tone": "focused",
            "tension_level": "medium"
        },
        interaction_pattern="Debate",
        initiative="Balanced between participants",
        emotional_shift="Tense → Resolved",
        open_loops=["Follow-up actions to assign"]
    )

    validator = EnrichmentValidator(default_config)
    report = validator.validate_chunk(chunk)

    # Detailed field analysis
    print("\nDetailed Field Analysis:\n")
    for field_name, field_result in report.field_results.items():
        print(f"{field_name.upper()}")
        print(f"  Value: {field_result.field_value}")
        print(f"  Score: {field_result.score:.2%}")
        print(f"  Valid: {field_result.is_valid}")
        if field_result.metadata:
            print(f"  Metadata: {field_result.metadata}")
        if field_result.issues:
            print(f"  Issues: {field_result.issues}")
        if field_result.warnings:
            print(f"  Warnings: {field_result.warnings}")
        print()


if __name__ == "__main__":
    print("\n" + "="*70)
    print("ENRICHMENT VALIDATION EXAMPLES")
    print("="*70)

    # Run all examples
    example_1_validate_single_chunk()
    example_2_validate_multiple_chunks()
    example_3_identify_patterns()
    example_4_field_by_field_analysis()

    print("\n" + "="*70)
    print("EXAMPLES COMPLETED")
    print("="*70)
    print("""
Key Takeaways:
1. Use EnrichmentValidator.validate_chunk() for single chunks
2. Use EnrichmentValidator.validate_chunks() for benchmarking
3. Each field is scored 0.0-1.0 based on quality metrics
4. Critical issues make chunks invalid (overall_validity = False)
5. Completeness tracks what % of fields are non-empty
6. Check issue_frequency in reports to identify systemic problems

For CLI Usage:
  python validate_enrichment.py --sample --size 50
  python validate_enrichment.py --sample --enrich --model ministral-8b
  python validate_enrichment.py --ground-truth ground_truth.json
    """)
