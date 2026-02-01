# Development Guide

## Environment Setup

1.  **Configuration:**
    - Copy `.env.example` to `.env`.
    - Run `python3 setup_env.py` for interactive configuration.

2.  **Dependencies:**
    - Backend: `pip install -r requirements.txt`
      - *Note:* For MLX acceleration (Apple Silicon), install: `pip install mlx mlx-lm`.
    - Frontend: `cd frontend && pnpm install`

## Workflow

### Data Pipeline (Indexing)
The RAG pipeline must be indexed before queries work.
1.  **Convert Export:** `python3 instagram_to_text.py`
2.  **Full Indexing:** `python3 setup_rag.py`
3.  **Check Status:** `python3 setup_rag.py --status`

### Running the Application
- **Backend:** `python3 app.py` (Port 8000)
- **Frontend:** `cd frontend && pnpm dev` (Port 5173)
- **CLI Chat:** `python3 cli.py`

## Code Conventions

- **Language:** Python 3.13+ (Backend), TypeScript/React 19 (Frontend).
- **Comments:** `rag_pipeline/` files often contain **French comments** (original codebase language). Preserve this style in that directory.
- **LLM Prompts:** Stored as string constants within their respective Python modules (e.g., `ENRICH_PROMPT`).
- **Paths:** Configurable via `.env` but default to `instagram_conversations/`, `rag_data/`, etc.
- **Formatting:** Adhere to project linting standards (pnpm lint for frontend).
