# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Local AI assistant for querying exported Instagram conversations using a RAG pipeline. Runs entirely locally with Ollama for LLM inference, FAISS + BM25 for hybrid search, and BGE-M3 for embeddings.

## Documentation Index

- **[Commands](docs/COMMANDS.md):** Build, run, test, and eval commands.
- **[Architecture](docs/ARCHITECTURE.md):** System modules, data flow, and tech stack.
- **[Development](docs/DEVELOPMENT.md):** Setup, workflow, and code conventions.
- **[RAG Pipeline](docs/RAG_PIPELINE.md):** Detailed indexing and query steps.
- **[Agents](AGENTS.md):** Details on the LLM agents (Enricher, Summarizer, etc.).

## Quick Reference

### Core Commands
- **Start Backend:** `python app.py`
- **Start Frontend:** `cd frontend && pnpm dev`
- **CLI Chat:** `python cli.py`
- **Full Indexing:** `python setup_rag.py`

### Testing
- **Unit Tests:** `pytest tests/`
- **Evaluation:** `python -m eval.eval_retrieval`

### Code Conventions
- **Comments:** French comments in `rag_pipeline/`.
- **Backend:** Python 3.13+, FastAPI, Pydantic v2.
- **Frontend:** React 19, TypeScript, pnpm.
- **LLM:** All calls via Ollama.