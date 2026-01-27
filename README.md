# Instagram Conversations Assistant

A production-ready local AI assistant to explore and query your exported Instagram conversations using advanced RAG (Retrieval-Augmented Generation).

## Features

- **Advanced RAG Pipeline**: Hybrid search (dense + BM25), cross-encoder reranking, context expansion
- **Modern Web Interface**: Multiple conversations, filters, real-time streaming
- **100% Local & Private**: No data sent to external servers
- **Production-Ready**: Evaluation pipeline, incremental updates, PII filtering, robustness features

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Index conversations (first time only)
python3 setup_rag_batch.py

# 3. Launch web application
python3 app.py

# 4. Open http://localhost:8000
```

## Architecture

```
instagram_conversations/     # Exported Instagram conversations
rag_data/
  ├── faiss_index/          # Vector store (dense search)
  ├── bm25_index.pkl        # Lexical index (keyword search)
  ├── metadata.db           # SQLite (metadata filtering)
  ├── file_state.json       # Delta tracker for incremental updates
  └── eval_dataset.json     # Evaluation dataset
rag_pipeline/               # Core RAG components
eval/                       # Evaluation pipeline (RAGAS metrics)
web/                        # Web interface
app.py                      # FastAPI server
```

## Key Commands

```bash
# View indexing status
python3 setup_rag_batch.py --status

# Incremental update (after adding/modifying files)
python3 update_index.py

# Full reindex from scratch
python3 setup_rag_batch.py --reset

# CLI chat interface
python3 cli.py

# Run evaluation benchmark
python -m eval.run_eval --benchmark
```

## Tech Stack

- **Embeddings**: BGE-M3 (multilingual FR/EN)
- **Vector Store**: FAISS
- **Reranker**: BGE-reranker-base
- **LLM**: Ollama (local)
- **Backend**: FastAPI
- **Frontend**: Vanilla JS

## Documentation

- [Quick Start Guide](docs/QUICKSTART.md)
- [Features Documentation](docs/FEATURES.md)
- [API Reference](docs/API.md)

## Privacy

Everything runs locally:
- Models downloaded once
- No external APIs
- Data stored only on your machine
