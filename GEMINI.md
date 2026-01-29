# Instagram Assistant Context

This `GEMINI.md` provides context for the Gemini CLI agent working on the Instagram Assistant project.

## Project Overview

**Instagram Assistant** is a local, privacy-focused RAG (Retrieval-Augmented Generation) application for exploring and querying exported Instagram conversations. It uses a hybrid search approach (Dense + BM25), hierarchical summarization, and a modern React frontend.

**Key Characteristics:**
- **Local-First:** Runs entirely on the user's machine (Ollama, local embeddings, FAISS).
- **RAG Pipeline:** Advanced two-stage retrieval with cross-encoder reranking and query analysis.
- **Multi-Agent:** Uses specialized "agents" (Enricher, Summarizer, Analyzer, Chat, Evaluator) for different pipeline stages.
- **Languages:** Python 3.13+ (Backend/Pipeline), TypeScript/React 19 (Frontend).

## Tech Stack

- **Backend:** Python (FastAPI), Pydantic v2.
- **Frontend:** React 19, TypeScript, Vite, TanStack Router, Tailwind CSS v4, Shadcn UI.
- **AI/ML:**
  - **LLM:** Ollama (default: `ministral-8b` for tasks, `qwen3:14b` for eval).
  - **Embeddings:** `BAAI/bge-m3`.
  - **Vector Store:** FAISS.
  - **Reranker:** `BAAI/bge-reranker-base`.
  - **Evaluation:** RAGAS-inspired custom pipeline.

## Development Workflow

### 1. Environment & Setup
*   **Config:** Managed via `.env` (template: `.env.example`).
*   **Setup Script:** `python3 setup_env.py` (Interactive configuration).
*   **Dependencies:**
    *   Backend: `pip install -r requirements.txt`
    *   Frontend: `cd frontend && pnpm install`

### 2. Data Pipeline (Indexing)
The RAG pipeline must be indexed before queries work.
*   **Convert Export:** `python3 instagram_to_text.py` (converts JSON export to text).
*   **Full Indexing:** `python3 setup_rag.py` (Runs chunking -> enrichment -> embeddings -> summaries).
*   **Check Status:** `python3 setup_rag.py --status`
*   **Reset:** `python3 setup_rag.py --reset`
*   **Incremental Update:** `python3 update_index.py` (after adding new exports).

### 3. Running the Application
*   **Backend API:** `python3 app.py` (FastAPI on port 8000).
*   **Frontend:** `cd frontend && pnpm dev` (Vite on port 5173).
*   **CLI Chat:** `python3 cli.py` (Interactive terminal chat).

### 4. Testing & Evaluation
*   **Unit Tests:** `pytest` (e.g., `pytest tests/`).
*   **Retrieval Eval:** `python -m eval.eval_retrieval`
*   **Generation Eval:** `python -m eval.eval_generation <model_name>`

## Architecture & Agents

The system relies on 5 specialized agents (defined in `AGENTS.md`):

1.  **Enricher** (`rag_pipeline/enricher.py`): Runs during indexing. Summarizes chunks, extracts entities/emotions, generates hypothetical questions.
2.  **Summarizer** (`rag_pipeline/summary_generator.py`): Runs post-indexing. Creates "Big Picture" hierarchical summaries (Conversation & Monthly levels).
3.  **Analyzer** (`rag_pipeline/query_analyzer.py`): "The Brain". Routes queries (retrieval vs. analytics), rewrites vague queries, and extracts dates.
4.  **Chat Assistant** (`rag_pipeline/chat.py`): Synthesizes answers from retrieved context. strictly anti-hallucination.
5.  **Evaluator** (`eval/models.py`): "The Judge". LLM-as-a-Judge for measuring retrieval/answer quality.

## Code Conventions

*   **Comments:** `rag_pipeline/` files often contain **French comments** (original codebase language). Preserve this style or use English if clarifying complex logic.
*   **Frontend:** Uses `pnpm`. Start via `pnpm dev`. Strict TypeScript usage.
*   **LLM Prompts:** stored as string constants within their respective Python modules.
*   **Paths:** All data paths are configurable via `.env` but default to `instagram_conversations/`, `rag_data/`, etc.

## Key Directories

*   `rag_pipeline/`: Core logic (Chunking, Embedding, Search, Chat).
*   `api/`: FastAPI routes and dependencies.
*   `frontend/`: React application.
*   `eval/`: Evaluation scripts and datasets.
*   `rag_data/`: **Gitignored**. Stores FAISS indexes, SQLite DBs, and cached summaries.
