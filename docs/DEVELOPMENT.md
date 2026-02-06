# Development Guide

## Environment Setup

1.  **Configuration:**
    - Copy `.env.example` to `.env`.
    - Run `python scripts/setup/setup_env.py` for interactive configuration.

2.  **Dependencies:**
    - **Recommended:** Use a virtual environment to avoid version conflicts (especially with MLX/Transformers).
    - Backend: 
      ```bash
      python3 -m venv .venv
      source .venv/bin/activate
      pip install -r requirements.txt
      ```
      - *Note:* For MLX acceleration (Apple Silicon), the requirements should include `mlx-lm`.
    - Frontend: `cd frontend && pnpm install`

### Initial Setup

```bash
# 1. Create a dedicated virtual environment (Mandatory recommended)
python3 -m venv .venv

# 2. Activate and install
source .venv/bin/activate
pip install -r requirements.txt

# Alternative: use the Makefile
make install
```

### ⚠️ Important: MLX Environment Issues
If you encounter errors like `ValueError: Tokenizer class TokenizersBackend does not exist` or other library version conflicts with MLX, **ensure you are using the project's virtual environment (`.venv`)**. Global Python environments often have conflicting `transformers` versions.

To fix environment issues:
1. Delete the existing environment: `rm -rf .venv`
2. Re-install: `make install`
3. Always run commands through `make` or with the `.venv` activated.

## Quick Access (Recommended)
- The project includes a `Makefile` that automatically uses the `.venv`.
- **Always prefer `make <command>`** or running through the `.venv` directly.
- Run `make help` to see available commands.

## Workflow

### Data Pipeline (Indexing)
The RAG pipeline must be indexed before queries work.
1.  **Convert Export:** `python scripts/ingestion/instagram_to_text.py`
2.  **Full Indexing:** `python scripts/setup/setup_rag.py`
3.  **Check Status:** `python scripts/setup/setup_rag.py --status`

### Running the Application
- **Backend:** `python app.py` (Port 8000)
- **Frontend:** `cd frontend && pnpm dev` (Port 5173)
- **CLI Chat:** `python cli.py`

## Code Conventions

- **Language:** Python 3.13+ (Backend), TypeScript/React 19 (Frontend).
- **Comments:** `rag_pipeline/` files often contain **French comments** (original codebase language). Preserve this style in that directory.
- **LLM Prompts:** Stored as string constants within their respective Python modules (e.g., `ENRICH_PROMPT`).
- **Paths:** Configurable via `.env` but default to `instagram_conversations/`, `rag_data/`, etc.
- **Formatting:** Adhere to project linting standards (pnpm lint for frontend).
