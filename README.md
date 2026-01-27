# Instagram Conversations Assistant

A production-ready local AI assistant to explore and query your exported Instagram conversations using advanced RAG (Retrieval-Augmented Generation).

## Features

- **Advanced RAG Pipeline**: Hybrid search (dense + BM25), cross-encoder reranking, context expansion
- **Modern Web Interface**: Multiple conversations, filters, real-time streaming
- **100% Local & Private**: No data sent to external servers
- **Production-Ready**: Evaluation pipeline, incremental updates, PII filtering, robustness features

## Quick Start

```bash
# 0. Configure environment (first time only)
python3 setup_env.py

# 1. Install dependencies
pip install -r requirements.txt

# 2. Convert Instagram conversations
python3 instagram_to_text.py

# 3. Index conversations
python3 setup_rag_batch.py

# 4. Launch web application
python3 app.py

# 5. Open http://localhost:8000
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

## Configuration

All paths are now configurable via environment variables:

```bash
# Interactive setup (recommended for first time)
python3 setup_env.py

# Or copy and edit manually
cp .env.example .env
```

See [Configuration Guide](docs/CONFIGURATION.md) for details.

## Key Commands

```bash
# Merge multiple Instagram exports (preserves all messages)
python3 merge_instagram_exports.py export1/ export2/ -o merged/

# Convert Instagram JSON to text
python3 instagram_to_text.py

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

## Merging Multiple Exports

Instagram limits exports to ~10k messages. To preserve all history when re-exporting:

```bash
# Merge old and new exports
python3 merge_instagram_exports.py \
    ~/Documents/old_export/messages/inbox \
    ~/Documents/new_export/messages/inbox \
    -o ~/Documents/merged/messages/inbox

# Preview without merging
python3 merge_instagram_exports.py old/ new/ -o merged/ --dry-run

# Update your .env to point to merged directory
# Then convert and reindex
python3 instagram_to_text.py
python3 update_index.py
```

The merge script:
- Deduplicates messages by timestamp
- Preserves all media files
- Keeps the most complete version of each message
- Shows statistics on duplicates removed

## Documentation

- [Configuration Guide](docs/CONFIGURATION.md)
- [Quick Start Guide](docs/QUICKSTART.md)
- [Features Documentation](docs/FEATURES.md)
- [API Reference](docs/API.md)

## Privacy

Everything runs locally:
- Models downloaded once
- No external APIs
- Data stored only on your machine
