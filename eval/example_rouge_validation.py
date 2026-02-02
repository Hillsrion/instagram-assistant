"""
Example: Using ROUGE-L to validate enriched narrative summaries.

This demonstrates:
1. Basic ROUGE-L score calculation
2. Validating summaries against ground truth references
3. Comparing different summary candidates
4. Interpreting ROUGE-L scores
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.chunker import Chunk
from rag_pipeline.config import default_config
from eval_enrichment import EnrichmentValidator, print_validation_report


def example_1_rouge_l_basics():
    """Example 1: Understanding ROUGE-L scores."""
    print("\n" + "="*70)
    print("EXAMPLE 1: ROUGE-L Basics")
    print("="*70)

    validator = EnrichmentValidator()

    # Test cases with different similarity levels
    test_cases = [
        {
            "name": "Perfect match",
            "reference": "Alice recommends a new restaurant to Bob",
            "candidate": "Alice recommends a new restaurant to Bob",
        },
        {
            "name": "Same meaning, different words",
            "reference": "Alice recommends a new restaurant to Bob",
            "candidate": "Alice suggests a different place to eat with Bob",
        },
        {
            "name": "Partial overlap",
            "reference": "Alice recommends a new restaurant to Bob on Main Street",
            "candidate": "Alice suggests going to a restaurant downtown",
        },
        {
            "name": "Minimal overlap",
            "reference": "Alice recommends a new restaurant to Bob",
            "candidate": "They discussed their weekend plans",
        },
        {
            "name": "No overlap",
            "reference": "Alice recommends a new restaurant to Bob",
            "candidate": "The weather was nice today",
        },
    ]

    for test in test_cases:
        rouge_l = validator.calculate_rouge_l(test["reference"], test["candidate"])
        word_overlap = validator.calculate_word_overlap(test["reference"], test["candidate"])

        print(f"\n{test['name']}:")
        print(f"  Reference: {test['reference']}")
        print(f"  Candidate: {test['candidate']}")
        print(f"  ROUGE-L:   {rouge_l:.2%}" if rouge_l is not None else "  ROUGE-L:   N/A (not installed)")
        print(f"  Overlap:   {word_overlap:.2%}")


def example_2_validate_with_ground_truth():
    """Example 2: Validate summaries against ground truth references."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Validating Against Ground Truth")
    print("="*70)

    # Create chunks with reference summaries (ground truth)
    chunks = [
        Chunk(
            chunk_id="chunk_001",
            conversation_id="conv_001",
            participants=["Alice", "Bob"],
            date_start="2024-01-15",
            date_end="2024-01-15",
            message_count=8,
            content="Alice: Hey Bob! Did you try that new restaurant on Main St?\nBob: Not yet, is it good?",
            file_source="test.txt",
            # Generated summary (from LLM)
            narrative_summary="Alice asks Bob about a restaurant on Main Street",
            # Reference summary (manually annotated ground truth)
            reference_summary="Alice inquires about a new restaurant on Main Street",
            hypothetical_questions=["What restaurant did Alice mention?"],
            speaker_intents={"Alice": "Ask opinion", "Bob": "Respond"},
            temporal_context="January 2024",
            entities={"locations": ["Main St"], "people": [], "media": [], "events": []},
            emotions={"dominant": "curiosity", "tone": "casual", "tension_level": "low"},
            interaction_pattern="Question-answer",
            initiative="Alice",
            emotional_shift="Stable",
            open_loops=[]
        ),
        Chunk(
            chunk_id="chunk_002",
            conversation_id="conv_002",
            participants=["Charlie", "Diana"],
            date_start="2024-01-20",
            date_end="2024-01-20",
            message_count=10,
            content="Charlie: Movie night? Diana: Yes! When? Charlie: Saturday at 8?",
            file_source="test.txt",
            # Generated summary (mediocre)
            narrative_summary="Planning event discussion",
            # Reference summary (ground truth)
            reference_summary="Charlie and Diana plan to watch a movie together on Saturday at 8pm",
            hypothetical_questions=["When is movie night?", "Who is attending?"],
            speaker_intents={"Charlie": "Propose movie night", "Diana": "Confirm plan"},
            temporal_context="Evening of January 20th",
            entities={"locations": [], "people": [], "media": ["Movie"], "events": ["Movie night"]},
            emotions={"dominant": "excitement", "tone": "enthusiastic", "tension_level": "low"},
            interaction_pattern="Planning",
            initiative="Balanced",
            emotional_shift="Neutral → Excited",
            open_loops=[]
        ),
        Chunk(
            chunk_id="chunk_003",
            conversation_id="conv_003",
            participants=["Eve", "Frank"],
            date_start="2024-01-25",
            date_end="2024-01-25",
            message_count=5,
            content="Eve: I got the job! Frank: Congrats!",
            file_source="test.txt",
            # Generated summary (very different)
            narrative_summary="Two people having a conversation",
            # Reference summary
            reference_summary="Eve shares good news about getting a job, Frank congratulates her",
            hypothetical_questions=["What is Eve's news?"],
            speaker_intents={"Eve": "Share success", "Frank": "Congratulate"},
            temporal_context="January 2024",
            entities={"locations": [], "people": [], "media": [], "events": []},
            emotions={"dominant": "joy", "tone": "positive", "tension_level": "low"},
            interaction_pattern="Story-telling",
            initiative="Eve",
            emotional_shift="Happy → Happier",
            open_loops=[]
        ),
    ]

    validator = EnrichmentValidator()
    report = validator.validate_chunks(chunks, verbose=True)

    # Show ROUGE-L details
    print("\n" + "="*70)
    print("ROUGE-L ANALYSIS")
    print("="*70)

    for chunk_report in report.chunk_reports:
        summary_result = chunk_report.field_results.get("narrative_summary")
        if summary_result and "rouge_l" in summary_result.metadata:
            rouge_l = summary_result.metadata["rouge_l"]
            print(f"\n{chunk_report.chunk_id}:")
            print(f"  Generated:  {summary_result.field_value}")
            print(f"  Reference:  {chunks[len(report.chunk_reports)-1].reference_summary if hasattr(chunks[0], 'reference_summary') else 'N/A'}")
            print(f"  ROUGE-L:    {rouge_l:.2%}")
            print(f"  Status:     {'✓ MATCH' if rouge_l > 0.6 else '⚠️  DIFFER' if rouge_l > 0.3 else '✗ VERY DIFFERENT'}")


def example_3_compare_candidates():
    """Example 3: Compare multiple summary candidates for the same chunk."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Comparing Multiple Summary Candidates")
    print("="*70)

    reference = "Alice recommends a new Italian restaurant to Bob and discusses their opening hours"

    candidates = [
        ("Generated by Ministral-8B", "Alice suggests new Italian restaurant, talks about hours"),
        ("Generated by Mixtral-8x7B", "Alice recommends Italian restaurant and mentions opening times"),
        ("Human summary", "Alice recommends a new Italian restaurant to Bob and discusses their opening hours"),
        ("Too short", "Restaurant recommendation"),
        ("Too long", "Alice was having a conversation with Bob about an Italian restaurant that recently opened. She mentioned it was a new restaurant and they discussed at length when the restaurant opens and closes each day of the week."),
    ]

    validator = EnrichmentValidator()

    print(f"\nReference: {reference}\n")
    print(f"{'Candidate':<30} {'ROUGE-L':<10} {'Overlap':<10} {'Rating':<15}")
    print("-" * 65)

    for name, candidate in candidates:
        rouge_l = validator.calculate_rouge_l(reference, candidate)
        overlap = validator.calculate_word_overlap(reference, candidate)

        if rouge_l is None:
            rating = "N/A"
            rouge_str = "N/A"
        else:
            rouge_str = f"{rouge_l:.2%}"
            if rouge_l > 0.7:
                rating = "✓ Excellent"
            elif rouge_l > 0.5:
                rating = "✓ Good"
            elif rouge_l > 0.3:
                rating = "⚠️  Fair"
            else:
                rating = "✗ Poor"

        print(f"{name:<30} {rouge_str:<10} {overlap:>6.0%}     {rating:<15}")
        print(f"  Candidate: {candidate}")


def example_4_batch_scoring():
    """Example 4: Score multiple summaries in batch."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Batch Scoring Summaries")
    print("="*70)

    # Create synthetic ground truth dataset
    ground_truth_pairs = [
        (
            "Alice recommends restaurant",
            ["Alice suggests restaurant", "Alice mentions new restaurant", "Food discussion"]
        ),
        (
            "They plan movie night",
            ["Movie night planning", "Planning to watch film", "Schedule discussion"]
        ),
        (
            "Job celebration",
            ["Eve got job", "Career success announcement", "New employment milestone"]
        ),
    ]

    validator = EnrichmentValidator()
    results = []

    for reference, candidates in ground_truth_pairs:
        print(f"\nReference: {reference}")
        for candidate in candidates:
            rouge_l = validator.calculate_rouge_l(reference, candidate)
            results.append((reference, candidate, rouge_l))
            rating = "✓" if rouge_l and rouge_l > 0.5 else "✗" if rouge_l else "N/A"
            score_str = f"{rouge_l:.2%}" if rouge_l is not None else "N/A"
            print(f"  {rating} {candidate:<30} ROUGE-L: {score_str}")

    # Statistics
    print("\n" + "="*70)
    print("BATCH STATISTICS")
    print("="*70)
    scores = [r[2] for r in results if r[2] is not None]
    if scores:
        avg_score = sum(scores) / len(scores)
        high_matches = sum(1 for s in scores if s > 0.6)
        print(f"Total pairs scored: {len(results)}")
        print(f"Average ROUGE-L: {avg_score:.2%}")
        print(f"High matches (>60%): {high_matches}/{len(scores)}")


def example_5_interpretation_guide():
    """Example 5: Understanding ROUGE-L scores."""
    print("\n" + "="*70)
    print("EXAMPLE 5: ROUGE-L Score Interpretation")
    print("="*70)

    print("""
ROUGE-L Score Ranges:

1.0 (100%)  ✓ Perfect match or functionally identical summaries
            Examples:
            - Reference: "Alice recommends restaurant"
            - Candidate: "Alice recommends restaurant"

0.8-0.99    ✓ Excellent similarity, same content and order
            Examples:
            - Reference: "Alice recommends Italian restaurant"
            - Candidate: "Alice recommends a Italian restaurant"

0.6-0.79    ✓ Good match, main ideas preserved, some wording changes
            Examples:
            - Reference: "Alice recommends restaurant to Bob"
            - Candidate: "Alice suggests a restaurant for Bob"

0.4-0.59    ⚠️  Fair match, similar concepts but structural differences
            Examples:
            - Reference: "Alice recommends restaurant on Main St"
            - Candidate: "Restaurant on Main St recommended by Alice"

0.2-0.39    ✗ Poor match, minimal overlap but related topics
            Examples:
            - Reference: "Alice recommends restaurant"
            - Candidate: "They discussed dining options"

0.0-0.19    ✗ Very poor match, almost no overlap
            Examples:
            - Reference: "Alice recommends restaurant"
            - Candidate: "Weather is nice today"

Key Points:

1. **Order matters**: ROUGE-L rewards same word order
   - "A loves B" scores higher than "B loves A"

2. **Stemming**: Words are stemmed, so "running" = "run"

3. **Content over form**: Synonyms won't match
   - "recommends" ≠ "suggests" (different stems)

4. **Useful for**:
   - Comparing generated summaries to reference summaries
   - Evaluating consistency of enrichment
   - Quality control on batch processing

5. **Limitations**:
   - Doesn't understand meaning (semantic similarity)
   - Penalizes paraphrasing heavily
   - Best used with ground truth data
""")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("ROUGE-L VALIDATION EXAMPLES")
    print("="*70)

    example_1_rouge_l_basics()
    example_2_validate_with_ground_truth()
    example_3_compare_candidates()
    example_4_batch_scoring()
    example_5_interpretation_guide()

    print("\n" + "="*70)
    print("EXAMPLES COMPLETED")
    print("="*70)
    print("""
Key Takeaways:

1. Use ROUGE-L when you have reference summaries (ground truth)
2. Add 'reference_summary' field to Chunk to enable automatic validation
3. ROUGE-L > 0.6 = good match, < 0.3 = significant differences
4. Use word_overlap() as fallback when ROUGE not installed
5. ROUGE-L is strict about word order and stemming

Next Steps:
1. Annotate 50-100 chunks with reference summaries manually
2. Run: validator.validate_chunks(chunks) to get ROUGE-L scores
3. Analyze which models produce high-scoring summaries
4. Use as quality gate in CI/CD pipelines
    """)
