# RAG Pipeline Summary

This document provides a concise end-to-end overview of the RAG pipeline. For detailed information on individual features, see [FEATURES.md](FEATURES.md). For the LLM agents involved at each stage, see [../AGENTS.md](../AGENTS.md).

---

## Stage 1: Indexing (Offline)

Orchestrated by `setup_rag.py`, runs sequentially:

### Step 1 — Chunking (`rag_pipeline/chunker.py`)

Splits raw `.txt` conversation files into `Chunk` objects using adaptive rules:
- **Temporal gap**: a silence of >6 hours forces a new chunk
- **Size cap**: max 50 messages or 3 days per chunk
- **Overlap**: 5 messages carried over between size-based splits (not temporal breaks)

Each chunk stores: participants, timestamps, message count, file source, and empty enrichment slots.

### Step 2 — LLM Enrichment (`rag_pipeline/enricher.py`)

The **Enricher agent** (Ollama, `ministral-8b`) processes each chunk with a strict JSON prompt and extracts:

| Field | Purpose |
|-------|---------|
| `narrative_summary` | 1-sentence narrative summary of the exchange |
| `hypothetical_questions` | 1 to 5 user-like questions this chunk answers (boosts semantic recall) |
| `speaker_intents` | Maps each participant to their inferred goal in the chunk |
| `temporal_context` | Semantic time anchor ("during vacation", "before moving") |
| `emotions` | Dominant emotion, tone, tension level |
| `entities` | Locations, people, media, events |

Checkpoints every 20 chunks for fault tolerance.

### Step 3 — Embedding (`rag_pipeline/embeddings.py`)

Each chunk's `get_embedding_text()` method builds a composite string prioritized as:
1. Hypothetical questions (highest signal)
2. Temporal context
3. Entities / Speaker intents / Emotions
4. Narrative summary
5. Raw message content

Encoded via **BGE-M3** (1024-dim, multilingual FR/EN), L2-normalized for cosine similarity.

### Steps 4–6 — Index Construction

Three parallel indexes are built from the enriched chunks:

| Index | Module | Technology | Role |
|-------|--------|------------|------|
| Dense vectors | `vector_store.py` | FAISS `IndexFlatIP` | Semantic similarity search |
| Lexical | `bm25_index.py` | BM25Okapi | Keyword/exact-match search |
| Metadata | `metadata_store.py` | SQLite | Filtering by participant, date, conversation |

### Steps 7–8 — Hierarchical Summaries (`rag_pipeline/summary_generator.py` + `summary_store.py`)

The **Summarizer agent** generates two levels of summaries from the enriched chunk narratives:

- **Conversation-level** (1 per contact): overall topics, relationship dynamic, notable events
- **Period-level** (1 per month per contact): monthly topics, mood, key events

Both levels are embedded and stored in dedicated FAISS indexes for fallback retrieval.

---

## Stage 2: Query Processing (Online)

### Step 1 — Query Analysis (`rag_pipeline/query_analyzer.py`)

The **Analyzer agent** performs 4 tasks in a single LLM call ("omni-prompt"):

1. **Routing**: `retrieval` (factual search) vs `analytics` (counting/stats via SQL)
2. **Rewriting**: resolves pronouns and conversational context into a standalone query
3. **Intent classification**: `specific_fact` (top_k=5) / `broad_summary` (top_k=15) / `complex_reasoning` (top_k=10)
4. **Date extraction**: natural language ("last summer") to ISO date range

### Step 2 — Hybrid Retrieval (`rag_pipeline/advanced_retriever.py`)

A 5-stage pipeline:

```
1. Pre-filter     → SQLite narrows candidates by participant/date/conversation
2. Hybrid search  → FAISS dense + BM25 lexical, blended at alpha=0.5, initial_k=20
3. Reranking      → Cross-encoder (bge-reranker-base) rescores top candidates
                     Final score = 50% hybrid + 50% reranker
4. Expansion      → Adjacent temporal chunks added at 0.5x score
5. Fallback       → If max score < 0.35, search hierarchical summaries
```

The **Reranker** (`rag_pipeline/reranker.py`) feeds the cross-encoder a rich document constructed from all enrichment fields (hypothetical questions, temporal context, intents, emotions, summary, content excerpt).

### Step 3 — Answer Generation (`rag_pipeline/chat.py`)

The **Chat Assistant agent** receives the formatted context (detailed chunks + summary fallback if triggered) and generates a response under strict anti-hallucination rules:
- Answer only from provided documents
- Refuse explicitly if information is absent
- Filter PII from output (`rag_pipeline/pii_filter.py`)

After the main response, a lighter prompt generates 3 follow-up question suggestions. Conversation history is auto-compacted beyond 10 messages (old turns are summarized, last 4 kept verbatim).

---

## Visual Overview

```
INDEXING                                         QUERY
────────                                         ─────
.txt files                                       User question
   │                                                │
   ▼                                                ▼
Chunker ──► Enricher (LLM) ──► Embeddings       Analyzer (omni-prompt)
               │                    │                │
               │                    ▼                ▼
               │              FAISS index ◄──── Hybrid search (dense+BM25)
               │              BM25 index             │
               │              SQLite metadata        ▼
               │                                 Reranker (cross-encoder)
               ▼                                     │
         Summary Generator                           ▼
               │                              Context expansion
               ▼                                     │
         Summary FAISS ◄─── (fallback) ◄─── Confidence check
                                                     │
                                                     ▼
                                              Chat Assistant (LLM)
                                                     │
                                                     ▼
                                              Answer + follow-ups
```
