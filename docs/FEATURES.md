# Instagram Assistant - Features Documentation

This document describes the advanced features of the Instagram Assistant RAG system.

---

## Table of Contents

1. [Evaluation Pipeline](#1-evaluation-pipeline)
2. [Robustness & Confidence](#2-robustness--confidence)
3. [Incremental Updates](#3-incremental-updates)
4. [User Experience](#4-user-experience)

---

## 1. Evaluation Pipeline

The evaluation pipeline enables automated measurement and comparison of RAG system performance.

### 1.1 Synthetic Data Generation

Module: `eval/synthetic_generator.py`

Automatically generates question-answer pairs from indexed chunks using an LLM.

#### Question Types

| Type | Description | Example |
|------|-------------|---------|
| `factual` | Direct information extraction | "When did you discuss X?" |
| `summary` | Synthesis question | "What did you discuss in January?" |
| `implicit` | Light inference | "What was the mood of this conversation?" |
| `temporal` | Time-based questions | "When did you plan Y?" |

#### Difficulty Levels

- `EASY`: Simple fact retrieval
- `MEDIUM`: Requires connecting information
- `HARD`: Requires inference or synthesis

#### Usage

```python
from eval.synthetic_generator import SyntheticDataGenerator

generator = SyntheticDataGenerator()
qa_pairs = generator.generate_dataset(chunks, target_size=50)
generator.save_dataset(qa_pairs)
```

### 1.2 RAGAS Metrics

Module: `eval/metrics.py`

Implements RAGAS-inspired metrics for RAG evaluation:

| Metric | Description | Range |
|--------|-------------|-------|
| **Retrieval Accuracy** | Is correct chunk in top-k? | 0-100% |
| **MRR** (Mean Reciprocal Rank) | Average reciprocal rank | 0-1 |
| **Faithfulness** | Is answer faithful to sources? (LLM-as-judge) | 0-1 |
| **Answer Relevance** | Does answer address the question? (LLM-as-judge) | 0-1 |

Metrics are broken down by question type and difficulty level.

### 1.3 Benchmark Runner

Module: `eval/benchmark.py`

Compare different RAG configurations:

```python
from eval.benchmark import BenchmarkRunner, BenchmarkConfig

runner = BenchmarkRunner()

config = BenchmarkConfig(
    name="full_pipeline",
    use_query_rewriting=True,
    use_reranking=True,
    use_hybrid=True,
    use_context_expansion=True,
    top_k=5
)

report = runner.run_benchmark(qa_pairs, config)
print(report.summary())
```

### 1.4 CLI Evaluation

```bash
# Generate 50 QA pairs
python -m eval.run_eval --generate 50

# Run benchmark
python -m eval.run_eval --benchmark

# Compare configurations (full, no_reranking, no_hybrid, minimal)
python -m eval.run_eval --compare
```

#### Example Output

```
=== Benchmark Report: full ===
Total questions: 50

Retrieval Metrics:
  Accuracy (Hit@k): 82.0%
  MRR: 0.756
  Avg Rank: 1.45

Generation Metrics:
  Faithfulness: 87.5%
  Relevance: 91.2%
```

---

## 2. Robustness & Confidence

### 2.1 Confidence Thresholds

The system can refuse to answer if confidence is too low.

#### Configuration

```python
# In rag_pipeline/config.py
confidence_threshold: float = 0.25  # Minimum required score
```

#### Behavior

- If `max_score < confidence_threshold`: Returns refusal message
- `low_confidence` flag added to retrieval context
- Web interface displays warning badge

### 2.2 Anti-Hallucination Prompt

The system prompt enforces strict truthfulness rules:

```
STRICT TRUTH RULES:

1. ABSOLUTE TRUTHFULNESS - Answer ONLY from provided documents
2. Mandatory refusal formulas:
   - "I did not find this information..."
   - "The provided documents do not contain..."
3. Cite sources with number and date
4. Protect personal data
5. Off-topic questions: polite refusal
```

### 2.3 PII Filtering

Module: `rag_pipeline/pii_filter.py`

Detects and masks personal information in responses.

#### Detected PII Types

| Type | Pattern | Mask |
|------|---------|------|
| French Phone | `06 12 34 56 78`, `+33...` | `[PHONE MASKED]` |
| Email | `user@domain.com` | `[EMAIL MASKED]` |
| IBAN | `FR76 3000 6000...` | `[IBAN MASKED]` |
| Credit Card | `4111 1111 1111 1111` | `[CARD MASKED]` |
| Address | `12 rue de Paris, 75001` | `[ADDRESS MASKED]` |
| French SSN | `1 85 12 75 115...` | `[SSN MASKED]` |

#### Usage

```python
from rag_pipeline.pii_filter import PIIFilter

filter = PIIFilter()

# Detect PII
matches = filter.detect(text)

# Mask PII
masked_text, matches = filter.mask(text)

# Check for PII
has_pii = filter.has_pii(text)
```

#### Enable/Disable

```python
# In rag_pipeline/config.py
enable_pii_filter: bool = True
```

---

## 3. Incremental Updates

### 3.1 Delta Tracker

Module: `rag_pipeline/delta_tracker.py`

Tracks file changes using SHA256 hashing.

#### How It Works

1. **SHA256 hash** of each indexed file
2. **Change detection**:
   - New files (not tracked)
   - Modified files (hash changed)
   - Deleted files (tracked but missing)

#### Persistent State

State saved in `rag_data/file_state.json`:

```json
{
  "last_updated": "2024-01-15T10:30:00",
  "total_files": 42,
  "files": {
    "/path/to/conversation.txt": {
      "content_hash": "abc123...",
      "last_modified": "2024-01-15T09:00:00",
      "last_indexed": "2024-01-15T10:00:00",
      "chunk_ids": ["conv_chunk_000", "conv_chunk_001"],
      "file_size": 15234
    }
  }
}
```

### 3.2 Incremental Vector Store

Module: `rag_pipeline/vector_store.py`

New methods for incremental updates:

```python
# Add vectors
vector_store.add_vectors(new_chunks, new_embeddings)

# Remove vectors by chunk_id
vector_store.remove_vectors(["chunk_001", "chunk_002"])

# Combined update (remove + add)
removed, added = vector_store.update_vectors(
    chunk_ids_to_remove=["old_chunk"],
    new_chunks=[new_chunk],
    new_embeddings=embeddings
)
```

### 3.3 Update Script

```bash
# Show status (detected changes)
python update_index.py --status

# Run incremental update
python update_index.py

# Force full rebuild
python update_index.py --full
```

#### Example Output

```
============================================================
Incremental Index Update
============================================================

Changes detected: New: 2, Modified: 1, Deleted: 0

Loading components...
Removing 15 old chunks...

Processing 3 files...
  [1/3] new_conversation.txt
  [2/3] updated_conversation.txt
  [3/3] another_new.txt

Enriching 45 chunks...

Generating embeddings for 45 chunks...
  [45/45] Done

Saving vector store...
Rebuilding BM25 index...
Rebuilding metadata index...
Saving tracker state...

============================================================
Update Complete
============================================================
Total chunks in index: 1250
Tracked files: 44
```

---

## 4. User Experience

### 4.1 Interactive Citations

Sources are clickable and display a modal with full content.

#### API Endpoint

```
GET /api/chunks/{chunk_id}
```

**Response**:
```json
{
  "chunk_id": "conv_chunk_001",
  "content": "...",
  "summary": "...",
  "participants": ["Alice", "Bob"],
  "date_start": "2024-01-15 10:00:00",
  "date_end": "2024-01-15 12:30:00",
  "file_source": "conversation_alice.txt",
  "message_count": 45,
  "hypothetical_questions": [
    "When did Alice and Bob discuss X?",
    "..."
  ]
}
```

#### Interface

- Click on source → Modal with full content
- Display: summary, metadata, hypothetical questions
- Raw conversation content

### 4.2 Follow-up Questions

System automatically generates 3 follow-up questions after each answer.

#### SSE Event

```json
{"type": "followups", "questions": [
  "Do you have other conversations on this topic?",
  "When did you discuss X again?",
  "Who else participated in this discussion?"
]}
```

#### Interface

- Clickable buttons below answer
- Click → Fills input field and submits automatically

### 4.3 Progress Indicators

Streaming now includes progress events:

| Step | Message |
|------|---------|
| `search` | "Searching..." |
| `documents` | "Reading N documents..." |
| `generating` | "Generating response..." |
| `followups` | "Preparing suggestions..." |

#### SSE Event

```json
{"type": "progress", "step": "documents", "message": "Reading 5 documents...", "count": 5}
```

### 4.4 Low Confidence Handling

When confidence score is too low:

1. No LLM call made
2. Immediate message: "I did not find relevant information..."
3. `low_confidence` badge in response metadata

---

## Architecture

```
instagram-assistant/
├── eval/
│   ├── synthetic_generator.py   # QA generation
│   ├── metrics.py               # RAGAS metrics
│   ├── benchmark.py             # Benchmark runner
│   └── run_eval.py              # CLI
├── rag_pipeline/
│   ├── config.py                # + confidence_threshold, enable_pii_filter
│   ├── advanced_retriever.py    # + low_confidence, max_confidence_score
│   ├── chat.py                  # + followup, PII filter
│   ├── vector_store.py          # + add/remove/update vectors
│   ├── pii_filter.py            # NEW: PII filtering
│   └── delta_tracker.py         # NEW: File tracking
├── web/
│   ├── index.html               # + Source modal
│   └── static/
│       ├── app.js               # + Progress, followups, modal
│       └── style.css            # + New component styles
├── update_index.py              # NEW: Incremental update script
└── docs/
    └── FEATURES.md              # This documentation
```

---

## FAQ

### How to disable PII filtering?

```python
# In config.py or at instantiation
config.enable_pii_filter = False
```

### How to adjust confidence threshold?

```python
# Stricter (refuses more often)
config.confidence_threshold = 0.4

# More permissive
config.confidence_threshold = 0.15
```

### Incremental update doesn't detect changes?

Verify:
1. Files are in `instagram_conversations/`
2. Extension is `.txt`
3. Content actually changed (not just date)

### How to force full rebuild?

```bash
python update_index.py --full
```

Or delete `rag_data/file_state.json` then run `update_index.py`.
