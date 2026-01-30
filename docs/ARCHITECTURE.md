# System Architecture

## Core Modules

- **`rag_pipeline/config.py`**
  Centralized `Config` dataclass. All settings flow from environment variables via `.env`. The singleton `default_config` is used throughout the application.

- **`rag_pipeline/query_analyzer.py`**
  The "Omni-prompt" agent. Performs routing, rewriting, intent classification, and date extraction in a single LLM call to optimize latency.

- **`rag_pipeline/advanced_retriever.py`**
  Implements hybrid search combining FAISS dense vectors and BM25 lexical search with configurable weights. Handles cross-encoder reranking and context expansion.

- **`api/dependencies.py`**
  FastAPI dependency injection module. Responsible for initializing all pipeline components (vector store, models) once and providing them to route handlers.

- **`api/routes/`**
  Modular route handlers for different functional areas: chat, analytics, conversations, participants, and system status.

- **`eval/`**
  Evaluation pipeline using RAGAS-style metrics. Uses a separate "judge" LLM (default: `qwen3:14b`) to score performance.

## Data Flow & Storage

- **`rag_data/`** (Gitignored)
  Stores all generated indexes and cached data:
  - FAISS indexes (Dense vectors)
  - BM25 pickle files (Lexical index)
  - SQLite metadata database
  - JSON summaries

- **`instagram_conversations/`** (Gitignored)
  Contains the converted text files from Instagram JSON exports.

- **`eval/eval_dataset.json`** (Gitignored)
  Generated QA pairs used for evaluation. See `eval_dataset.sample.json` for the expected format.

## Tech Stack

- **Backend:** Python 3.13+, FastAPI, Pydantic v2.
- **Frontend:** React 19, TypeScript, Vite, TanStack Router, Tailwind CSS v4, Shadcn UI.
- **AI/ML:**
  - **LLM:** Ollama (default: `ministral-8b` for tasks, `qwen3:14b` for eval).
  - **Embeddings:** `BAAI/bge-m3`.
  - **Vector Store:** FAISS.
  - **Reranker:** `BAAI/bge-reranker-base`.
