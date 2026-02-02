# Enrichment Validation Guide

Comprehensive validation suite for chunk enrichment quality assessment.

## Overview

The enrichment validation system provides automated quality checks for all enrichment fields:

- **Narrative Summary**: Conciseness, content coverage
- **Hypothetical Questions**: Answerability, relevance, quantity
- **Speaker Intents**: Coverage of all participants, clarity
- **Temporal Context**: Format, meaningfulness
- **Entities**: Structure, categorical completeness, string types
- **Emotions**: Required fields (dominant, tone, tension_level), valid values
- **Interaction Pattern**: Valid classification
- **Initiative**: Participant alignment
- **Emotional Shift**: Trajectory format
- **Open Loops**: Unresolved topics format

## Quick Start

### Run Example Validation

```bash
# See all examples in action
python eval/example_enrichment_validation.py

# This runs 4 examples:
# 1. Single chunk validation
# 2. Benchmark across multiple chunks
# 3. Identify common issues
# 4. Field-by-field analysis
```

### Validate Chunks from Index

```bash
# Validate 20 random chunks from your index
python eval/validate_enrichment.py --sample --size 20

# Validate and show verbose output
python eval/validate_enrichment.py --sample --size 20 --verbose

# Validate AND re-enrich with a specific model
python eval/validate_enrichment.py --sample --size 50 --enrich --model ministral-8b
```

## Programmatic Usage

### Basic Usage

```python
from rag_pipeline.chunker import Chunk
from eval.eval_enrichment import EnrichmentValidator
from rag_pipeline.config import default_config

# Create or load a chunk with enrichment fields
chunk = Chunk(
    chunk_id="chunk_001",
    conversation_id="conv_001",
    participants=["Alice", "Bob"],
    date_start="2024-01-15",
    date_end="2024-01-15",
    message_count=8,
    content="Conversation text...",
    file_source="conversations/alice_bob.txt",
    # Enrichment fields
    narrative_summary="Alice recommends a restaurant to Bob",
    hypothetical_questions=[
        "What restaurant did Alice recommend?",
        "Where is it located?"
    ],
    speaker_intents={
        "Alice": "Share discovery about new place",
        "Bob": "Learn details about the restaurant"
    },
    temporal_context="January 2024, weekday afternoon",
    entities={
        "locations": ["Main St"],
        "people": [],
        "media": [],
        "events": []
    },
    emotions={
        "dominant": "enthusiasm",
        "tone": "casual",
        "tension_level": "low"
    },
    interaction_pattern="Information sharing",
    initiative="Alice leads",
    emotional_shift="Stable",
    open_loops=[]
)

# Validate the chunk
validator = EnrichmentValidator(default_config)
report = validator.validate_chunk(chunk)

# Check results
print(f"Valid: {report.overall_validity}")
print(f"Score: {report.overall_score:.2%}")
print(f"Completeness: {report.completeness:.2%}")

# Get detailed results
for field_name, field_result in report.field_results.items():
    print(f"{field_name}: {field_result.score:.2%}")
    if field_result.issues:
        print(f"  Issues: {field_result.issues}")
```

### Batch Validation

```python
from eval.eval_enrichment import EnrichmentValidator, print_benchmark_report

# Load or create multiple chunks
chunks = [...]

# Validate all chunks
validator = EnrichmentValidator(default_config)
benchmark_report = validator.validate_chunks(chunks, verbose=True)

# Print aggregate metrics
print_benchmark_report(benchmark_report)

# Access detailed results
print(f"Valid chunks: {benchmark_report.valid_chunks}/{benchmark_report.total_chunks}")
print(f"Average score: {benchmark_report.avg_overall_score:.2%}")

# Per-field metrics
for field, score in benchmark_report.field_scores.items():
    validity_rate = benchmark_report.field_validity_rates[field]
    print(f"{field}: {score:.2%} (validity: {validity_rate:.1%})")
```

## Understanding the Report

### Chunk-Level Report (`ChunkEnrichmentValidationReport`)

Each field has:

- **is_valid** (bool): No critical issues for this field
- **score** (0.0-1.0): Quality metric (1.0 = perfect)
- **issues** (list): Critical problems that make field invalid
- **warnings** (list): Quality concerns (field still valid)
- **metadata** (dict): Field-specific statistics

#### Overall Metrics

- **overall_validity**: All fields valid AND overall_score >= 0.5
- **overall_score**: Weighted average of field scores
- **completeness**: % of non-empty enrichment fields
- **summary**: Human-readable status description

### Benchmark Report (`EnrichmentBenchmarkReport`)

Aggregates results across multiple chunks:

- **valid_chunks**: Count of chunks with overall_validity=True
- **avg_overall_score**: Mean score across all chunks
- **avg_completeness**: Mean completeness across all chunks
- **field_scores**: Average score per field across all chunks
- **field_validity_rates**: % of chunks valid for each field
- **issue_frequency**: Which issues occur most often

### Example Report Output

```
==============================================================
ENRICHMENT VALIDATION: chunk_001
==============================================================
Conversation: conv_alice_bob
Overall Score: 85.00% | Completeness: 100.00%
Status: ✓ VALID
Issues: 0 | Warnings: 1

✓ NARRATIVE_SUMMARY (100.00%)
  📊 {'word_count': 8, 'sentence_count': 1}

✓ QUESTIONS (80.00%)
  ⚠️  Short questions (1): might be too vague
  📊 {'question_count': 3, 'avg_question_length': 5, ...}

✓ SPEAKER_INTENTS (100.00%)
  📊 {'speaker_count': 2, 'speakers': ['Alice', 'Bob']}

✓ TEMPORAL_CONTEXT (100.00%)
  📊 {'word_count': 6}

✓ ENTITIES (90.00%)
  ⚠️  Only 1 entity extracted, consider if more are relevant
  📊 {'total_entities': 1, 'categories': {...}}

✓ EMOTIONS (100.00%)
  📊 {'dominant_emotion': 'enthusiasm', 'tension_level': 'low'}

✓ INTERACTION_PATTERN (100.00%)
  📊 {'pattern': 'Information sharing'}

✓ INITIATIVE (100.00%)
  📊 {'initiative': 'Alice leads'}

✓ EMOTIONAL_SHIFT (100.00%)
  📊 {'shift': 'Stable'}

✓ OPEN_LOOPS (100.00%)
  📊 {'loop_count': 0}
```

## Field-Specific Validation Rules

### Narrative Summary
- **Critical**: Must be non-empty
- **Quality**: 5-30 words, should be 1 sentence
- **Score**: 1.0 (perfect) if 5-25 words, penalties for too long/short

### Hypothetical Questions
- **Critical**: Must be list of strings
- **Quality**: 1-5 questions, each 3-30 words
- **Score**: Based on count and length distribution

### Speaker Intents
- **Critical**: Must be dict of str→str
- **Quality**: Should include all chunk participants, 3-15 words each
- **Score**: Penalties for missing participants or very short intents

### Temporal Context
- **Critical**: Can be empty (warning only)
- **Quality**: 2-20 words, meaningful description
- **Score**: 0.5 if empty, 1.0 if 2-20 words

### Entities
- **Critical**: Must be dict with keys: locations, people, media, events
- **Quality**: All values must be lists of strings
- **Score**: Based on structure validity and population

### Emotions
- **Critical**: Should have dominant, tone, tension_level
- **Quality**: tension_level must be "low"/"medium"/"high"
- **Score**: 1.0 if all required fields valid, penalties otherwise

### Interaction Pattern
- **Critical**: Can be null (acceptable)
- **Quality**: Should match predefined patterns
- **Score**: 0.6 if null, 1.0 if valid pattern, 0.7 if unknown

### Initiative
- **Critical**: Can be null (acceptable)
- **Quality**: Should reference participant names or be "Balanced"
- **Score**: Similar to interaction_pattern

### Emotional Shift
- **Critical**: Can be null (acceptable)
- **Quality**: Should use "X → Y" format or be "Stable"
- **Score**: 1.0 if valid format, 0.7 otherwise

### Open Loops
- **Critical**: Must be list of strings (empty list is valid)
- **Quality**: Each item should be 3+ words
- **Score**: Based on item validity and count

## Interpreting Scores

| Score | Interpretation | Action |
|-------|---|---|
| 1.0 | Perfect | No action needed |
| 0.8-0.99 | Good | Minor issues, acceptable |
| 0.7-0.79 | Fair | Review needed, consider improvements |
| 0.5-0.69 | Poor | Significant issues, needs fixing |
| < 0.5 | Critical | Invalid, requires fixes |

### Overall Chunk Validity

A chunk is **VALID** if:
- No critical issues across any field
- overall_score >= 0.5

Even with warnings, a chunk is valid.

## Common Issues & Solutions

### Issue: Low Entity Extraction Scores

**Symptom**: Only 1-2 entities across all categories

**Causes**:
- LLM being too conservative (avoiding hallucination)
- Conversation has few mentioned entities
- Prompt not emphasizing what to extract

**Solution**:
```python
# Check if it's intentional
if chunk.content has few entity mentions:
    # This is expected, score is appropriate

# If LLM is too conservative:
# Adjust ENRICH_PROMPT in rag_pipeline/enricher.py
# Add example with more entities
```

### Issue: Very Short Questions

**Symptom**: Questions with < 5 words, seems incomplete

**Causes**:
- Fragmented conversation with short exchanges
- LLM generating non-questions
- Tokenization issues

**Solution**:
```python
# Check raw text
if chunk.content has only short messages:
    # Expected, questions will be short

# Otherwise, adjust prompt to request more detailed questions
```

### Issue: Missing Speaker Intents

**Symptom**: Only 1-2 intents despite multiple participants

**Causes**:
- Some participants barely speak
- Intents are too similar to summarize separately
- Prompt ambiguity

**Solution**:
```python
# Valid if quiet participants have minimal role
if participant_message_count < 2:
    # Acceptable to skip
```

### Issue: Invalid Temporal Context

**Symptom**: Context doesn't match chunk date_start/date_end

**Causes**:
- LLM inferring wrong time period
- Conversation references different timeframe than sent

**Solution**:
```python
# Add validation to compare temporal context with actual dates
if chunk.date_start not in temporal_context:
    # Might be acceptable (e.g., "during vacation" is valid)
```

## Ground Truth Validation

Compare predictions against manually annotated ground truth:

```python
# Ground truth format (JSON)
ground_truth = [
    {
        "chunk_id": "chunk_001",
        "expected_questions": [
            "What restaurant did Alice recommend?",
            "Where is it?"
        ],
        "expected_entities": {
            "locations": ["Main St", "Restaurant"],
            "people": [],
            "media": [],
            "events": []
        },
        "expected_emotion": "enthusiasm"
    }
]

# Compare
python eval/validate_enrichment.py --ground-truth ground_truth.json --size 50
```

## Running Continuous Validation

### As Part of Pipeline

```python
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.enricher import ChunkEnricher
from eval.eval_enrichment import EnrichmentValidator

# Your normal pipeline
chunker = ConversationChunker(config)
enricher = ChunkEnricher(config)

chunks = chunker.process_conversations()
enricher.enrich_all_chunks(chunks)

# Add validation check
validator = EnrichmentValidator(config)
report = validator.validate_chunks(chunks)

if report.avg_overall_score < 0.7:
    print("⚠️  Warning: Low enrichment quality detected")
    print(f"Score: {report.avg_overall_score:.2%}")
    print(f"Issues: {report.total_critical_issues}")
```

### As GitHub Workflow

```yaml
# .github/workflows/validate-enrichment.yml
name: Validate Enrichment Quality

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run enrichment validation
        run: |
          python eval/validate_enrichment.py --sample --size 100
          # Fail if score drops below threshold
```

## Performance Benchmarks

Expected scores by enrichment complexity:

| Aspect | Expected Score | Notes |
|--------|---|---|
| Simple conversations | 0.85-0.95 | Few participants, clear intent |
| Complex conversations | 0.70-0.85 | Multiple topics, unclear intent |
| Highly enriched | 0.80-0.95 | Many entities, clear emotions |
| Minimal content | 0.60-0.75 | Few entities, vague intent |

## API Reference

### EnrichmentValidator

```python
class EnrichmentValidator:
    def __init__(self, config: Config = None)

    def validate_chunk(self, chunk: Chunk) -> ChunkEnrichmentValidationReport
        """Validate single chunk"""

    def validate_chunks(self, chunks: List[Chunk], verbose: bool = False)
        -> EnrichmentBenchmarkReport
        """Validate multiple chunks"""
```

### Report Classes

```python
@dataclass
class ChunkEnrichmentValidationReport:
    chunk_id: str
    overall_validity: bool  # Is chunk valid?
    overall_score: float    # 0.0-1.0
    completeness: float     # % of fields filled
    field_results: Dict[str, FieldValidationResult]

@dataclass
class EnrichmentBenchmarkReport:
    total_chunks: int
    valid_chunks: int
    avg_overall_score: float
    avg_completeness: float
    field_scores: Dict[str, float]  # Per-field average
    field_validity_rates: Dict[str, float]  # % chunks valid per field
    issue_frequency: Dict[str, int]  # Which issues occur most
```

## Troubleshooting

### "No chunks found in index"

Ensure you've run `python setup_rag.py` to index conversations.

### Validation is too strict / too lenient

Adjust thresholds in `eval_enrichment.py`:
- `_validate_*` methods contain scoring logic
- Modify penalty multipliers to adjust strictness
- Add custom validators for your use case

### Want custom validation rules?

Extend EnrichmentValidator:

```python
class CustomValidator(EnrichmentValidator):
    def _validate_custom_field(self, value, chunk):
        result = FieldValidationResult(
            field_type=...,
            field_value=value,
            is_valid=True,
            score=1.0
        )
        # Add your logic
        return result
```

## See Also

- [ENRICHMENT_STRATEGY.md](../docs/EMBEDDING_STRATEGY.md) - Enrichment design rationale
- [RAG_PIPELINE.md](../docs/RAG_PIPELINE.md) - How enrichment fits in pipeline
- [AGENTS.md](../AGENTS.md) - Enricher agent details
