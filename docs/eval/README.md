# Evaluation Documentation

Comprehensive guides for evaluating enrichment quality.

## Contents

- **[Enrichment Validation](ENRICHMENT_VALIDATION.md)** - Complete validation framework for chunk enrichment
  - Validates 10 enrichment fields with quality scoring
  - Per-field scoring (0.0-1.0) and aggregated metrics
  - CLI tool and programmatic API
  - Benchmark reports and issue tracking


## Quick Start

See main [EVAL.md](../EVAL.md) for evaluation overview and CLI commands.

## Example Usage

### Validate Enrichment

```bash
python eval/example_enrichment_validation.py
python eval/validate_enrichment.py --sample --size 50
```


## Key Concepts

### Enrichment Fields (10 total)

1. **Narrative Summary** - Concise one-sentence summary
2. **Hypothetical Questions** - 1-5 questions the chunk answers
3. **Speaker Intents** - Each participant's main objective
4. **Temporal Context** - When relative to life events
5. **Entities** - Locations, people, media, events mentioned
6. **Emotions** - Dominant emotion, tone, tension level
7. **Interaction Pattern** - Type of exchange (Planning, Debate, etc.)
8. **Initiative** - Who leads conversation
9. **Emotional Shift** - Trajectory (e.g., "Neutral → Happy")
10. **Open Loops** - Unresolved topics

### Quality Scoring

- **0.0-1.0 scale** where 1.0 is perfect
- **Per-field scores** plus overall average
- **Completeness** tracking (% of fields non-empty)
- **Issues vs warnings** (critical vs informational)
- **Validity flag** (overall_validity = True if score ≥ 0.5 and no critical issues)

### Ground Truth Comparison

- **Word Overlap** (Jaccard similarity) between generated and reference summaries
- Scores 0.0-1.0 (1.0 = identical)
- Automatic when `reference_summary` field is present
- Useful for comparing enrichment models

## See Also

- [EVAL.md](../EVAL.md) - Main evaluation guide
- [RAG_PIPELINE.md](../RAG_PIPELINE.md) - How enrichment fits in pipeline
- [AGENTS.md](../../AGENTS.md) - Enricher agent details
