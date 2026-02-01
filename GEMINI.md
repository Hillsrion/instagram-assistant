# Instagram Assistant Context

This `GEMINI.md` provides context for the Gemini CLI agent working on the Instagram Assistant project.

## Project Overview

**Instagram Assistant** is a local, privacy-focused RAG (Retrieval-Augmented Generation) application for exploring and querying exported Instagram conversations. It uses a hybrid search approach (Dense + BM25), hierarchical summarization, and a modern React frontend.

**Key Characteristics:**
- **Local-First:** Runs entirely on the user's machine (Ollama + MLX, local embeddings, FAISS).
- **RAG Pipeline:** Advanced two-stage retrieval with cross-encoder reranking and query analysis.
- **Multi-Agent:** Uses specialized "agents" (Enricher, Summarizer, Analyzer, Chat, Evaluator).

## Documentation Index

- **[Commands](docs/COMMANDS.md):** Build, run, test, and eval commands.
- **[Architecture](docs/ARCHITECTURE.md):** System modules, data flow, and tech stack.
- **[Development](docs/DEVELOPMENT.md):** Setup, workflow, and code conventions.
- **[RAG Pipeline](docs/RAG_PIPELINE.md):** detailed breakdown of the indexing and query steps.
- **[Agents](AGENTS.md):** Details on the specific LLM agents and prompts.
- **[Configuration](docs/CONFIGURATION.md):** Environment variables and settings.

## Quick Reference

### Essentials
- **Backend:** `python3 app.py` (FastAPI on 8000)
- **Frontend:** `cd frontend && pnpm dev` (Vite on 5173)
- **CLI Chat:** `python3 cli.py`
- **Indexing:** `python3 setup_rag.py`

### Key Directories
- `rag_pipeline/`: Core logic (Chunking, Embedding, Search, Chat).
- `api/`: FastAPI routes and dependencies.
- `frontend/`: React application.
- `eval/`: Evaluation scripts.