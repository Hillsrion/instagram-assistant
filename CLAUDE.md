# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Local AI assistant for querying exported Instagram conversations using a RAG pipeline. Runs entirely locally with Ollama for LLM inference, FAISS + BM25 for hybrid search, and BGE-M3 for embeddings. See `AGENTS.md` for details on the 5 LLM agents (Enricher, Summarizer, Analyzer, Chat Assistant, Evaluator).

## Commands

### Backend
```bash
python3 app.py                    # FastAPI server on port 8000
python3 cli.py                    # Interactive CLI chat
python3 cli.py --prompt "query"   # Single query mode
```

### Frontend
```bash
cd frontend && pnpm install       # Install deps (first time)
cd frontend && pnpm dev           # Dev server on port 5173
cd frontend && pnpm build         # Production build
cd frontend && pnpm lint          # ESLint
```

### Indexing Pipeline
```bash
python3 setup_rag.py              # Full pipeline (all steps)
python3 setup_rag.py --status     # Show indexing progress
python3 setup_rag.py --reset      # Full reindex from scratch
python3 setup_rag.py --only chunks  # Run a single step
```

### Tests
```bash
pytest tests/                     # All unit tests
pytest tests/test_config.py       # Single test file
pytest tests/api/                 # API tests only
pytest tests/setup/               # Setup script tests
```

### Evaluation
```bash
python -m eval.generate_dataset 50                        # Generate QA dataset
python -m eval.eval_retrieval                             # Evaluate retrieval quality
python -m eval.eval_generation qwen3:latest mistral       # Compare model generation
python -m eval.eval_generation model1 model2 --trials 10  # Multiple trial runs
python -m eval.model_dashboard                            # Multi-model comparison dashboard
python -m eval.evaluate_summaries                         # Evaluate summary quality
```

## Architecture

### Two-Stage RAG Pipeline

**Indexing (offline):** Instagram JSON export → `instagram_to_text.py` → text files → `setup_rag.py` orchestrates: chunking → LLM enrichment (summaries, entities, hypothetical questions) → BGE-M3 embeddings → FAISS + BM25 indexes + SQLite metadata → hierarchical summaries (conversation-level + monthly).

**Query (online):** User question → `query_analyzer.py` (single LLM call for routing, rewriting, intent classification, date extraction) → `advanced_retriever.py` (hybrid FAISS dense + BM25 lexical search) → `reranker.py` (cross-encoder) → context expansion with adjacent chunks → confidence check with summary fallback → `chat.py` (final LLM response).

### Key Modules

- **`rag_pipeline/config.py`** — Centralized `Config` dataclass; all settings flow from env vars via `.env`. The singleton `default_config` is used throughout.
- **`rag_pipeline/query_analyzer.py`** — "Omni-prompt" that performs routing, rewriting, intent classification, and date extraction in one LLM call.
- **`rag_pipeline/advanced_retriever.py`** — Hybrid search combining dense vectors and BM25 with configurable weights, cross-encoder reranking, and context expansion.
- **`api/dependencies.py`** — FastAPI dependency injection; initializes all pipeline components once.
- **`api/routes/`** — Modular route handlers (chat, analytics, conversations, participants, status).
- **`eval/`** — Evaluation pipeline with RAGAS-style metrics; uses a separate "judge" LLM (default: `qwen3:14b`).

### Data Flow

- `rag_data/` — All indexes and cached data (FAISS, BM25 pickle, SQLite metadata, JSON summaries). Gitignored.
- `instagram_conversations/` — Converted text files from Instagram exports. Gitignored.
- `eval/eval_dataset.json` — Generated QA pairs for evaluation. Gitignored; see `eval_dataset.sample.json` for format.

## Configuration

All config via `.env` (run `python3 setup_env.py` for interactive setup). Key variables:
- `LLM_MODEL` / `LLM_MODEL_FAST` / `LLM_MODEL_STRONG` — Ollama model tiers
- `OLLAMA_URL` — Ollama server (default: `http://localhost:11434`)
- `EMBEDDING_MODEL` — Embedding model (default: `BAAI/bge-m3`)
- `USE_RERANKING` / `USE_HYBRID` — Toggle retrieval features
- `TOP_K` / `MIN_SIMILARITY` — Retrieval parameters

See `docs/CONFIGURATION.md` for the full reference.

## Code Conventions

- Python code uses French comments in `rag_pipeline/` (the original codebase language)
- Backend: Python 3.13+, FastAPI, Pydantic v2, dataclasses for internal models
- Frontend: React 19, TypeScript, TanStack Router + Query, Tailwind CSS v4, Shadcn UI, pnpm
- LLM prompts are stored as string constants in their respective module files (e.g., `ENRICH_PROMPT` in `enricher.py`, `SYSTEM_PROMPT` in `chat.py`)
- All LLM calls go through Ollama's HTTP API via the `ollama_url` config
