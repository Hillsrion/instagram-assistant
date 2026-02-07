# Enricher Agent ("The Indexer")

**Component:** `rag_pipeline/enricher.py`
**Trigger:** Data ingestion (`scripts/setup/setup_rag.py`)
**Default Model:** `ministral-8b`

The Enricher reads raw conversation chunks (batches of messages) and transforms them into rich, searchable documents.

## Capabilities

- **Narrative Summary:** Concise overview of the exchange.
- **Hypothetical Questions:** Generates 1 to 5 questions that this chunk answers (improves semantic search).
- **Speaker Intentions:** What each person wants.
- **Emotion Analysis:** Detects dominant emotion, tone, and tension level.
- **Temporal Context:** Identifies "when" this happened relative to life events (e.g., "vacation", "before moving").
- **Social Dynamics:**
  - **Interaction Pattern:** Type of exchange (e.g., "Planning", "Debate").
  - **Initiative:** Who leads the conversation?
  - **Emotional Shift:** Trajectory (e.g., "Neutral -> Happy").
  - **Open Loops:** Unresolved topics.

## Prompt Strategy

Uses a **Strict JSON** prompt (`ENRICH_PROMPT`) to force structured output. It is explicitly told to avoid hallucinations and only use provided text.

## Error Handling

- **Automatic Retry**: If the 3B model produces corrupted JSON (repetition loops, truncation), the system automatically retries with the 8B model.
- **Failure Tracking**: Chunks that fail even with 8B are marked `enrichment_failed=True` and skipped in future runs.
- **Graceful Degradation**: Failed chunks are still embedded using raw content only, preserving context for search.
