# Instagram Assistant Documentation

Welcome to the Instagram Assistant documentation, a production-ready RAG (Retrieval-Augmented Generation) system for analyzing Instagram conversations.

## Documentation Index

| Document | Description |
|----------|-------------|
| [Quick Start Guide](QUICKSTART.md) | Installation and first steps |
| [Features Documentation](FEATURES.md) | Comprehensive feature guide |
| [API Reference](API.md) | REST endpoints and SSE events |

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Instagram Assistant                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Web UI     │    │     CLI      │    │     API      │       │
│  │  (index.html)│    │   (cli.py)   │    │   (app.py)   │       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘       │
│         │                   │                   │                │
│         └───────────────────┴───────────────────┘                │
│                             │                                    │
│                    ┌────────▼────────┐                           │
│                    │    ChatBot      │                           │
│                    │  (chat.py)      │                           │
│                    └────────┬────────┘                           │
│                             │                                    │
│         ┌───────────────────┼───────────────────┐                │
│         │                   │                   │                │
│  ┌──────▼──────┐    ┌───────▼───────┐   ┌──────▼──────┐         │
│  │   Retriever │    │  PII Filter   │   │   Followup  │         │
│  │  (advanced) │    │               │   │  Generator  │         │
│  └──────┬──────┘    └───────────────┘   └─────────────┘         │
│         │                                                        │
│  ┌──────┴─────────────────────────────────┐                     │
│  │                                         │                     │
│  │  ┌─────────┐ ┌─────────┐ ┌──────────┐  │                     │
│  │  │  FAISS  │ │  BM25   │ │ Metadata │  │                     │
│  │  │  Index  │ │  Index  │ │  Store   │  │                     │
│  │  └─────────┘ └─────────┘ └──────────┘  │                     │
│  │                                         │                     │
│  │         Vector Store + Indices          │                     │
│  └─────────────────────────────────────────┘                     │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                     Auxiliary Tools                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ Delta Tracker│ │  Evaluator   │ │   Enricher   │             │
│  │              │ │  (RAGAS)     │ │   (LLM)      │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## Core Features

### 1. Hybrid Search
- Dense search (FAISS embeddings)
- Lexical search (BM25)
- Cross-encoder reranking
- Context expansion with adjacent chunks

### 2. Robustness
- Configurable confidence thresholds
- Automatic PII filtering (7 types detected)
- Anti-hallucination prompts
- Strict source citation requirements

### 3. Incremental Updates
- Automatic change detection (SHA256 hashing)
- Partial indexing (add/modify/delete)
- Persistent state tracking
- No full reindex needed

### 4. Automated Evaluation
- Synthetic QA pair generation
- RAGAS metrics (Accuracy, MRR, Faithfulness, Relevance)
- Configuration comparison
- Benchmark reports

### 5. Enhanced UX
- Streaming with progress indicators
- Interactive citations (clickable sources)
- Auto-generated follow-up questions
- Real-time updates via SSE

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI, Python 3.10+ |
| LLM | Ollama (local) |
| Embeddings | BGE-M3 (multilingual) |
| Vector Store | FAISS |
| Lexical Search | rank_bm25 |
| Reranker | BGE-reranker-base |
| Frontend | Vanilla JS, CSS |

## Getting Started

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Index conversations**: `python setup_rag_batch.py`
3. **Launch app**: `python app.py`
4. **Open browser**: http://localhost:8000

## Project Structure

```
instagram-assistant/
├── app.py                  # FastAPI server
├── cli.py                  # CLI interface
├── setup_rag_batch.py      # Initial indexing
├── update_index.py         # Incremental updates
├── rag_pipeline/           # Core RAG components
│   ├── config.py
│   ├── chunker.py
│   ├── embeddings.py
│   ├── vector_store.py
│   ├── advanced_retriever.py
│   ├── chat.py
│   ├── pii_filter.py
│   └── delta_tracker.py
├── eval/                   # Evaluation pipeline
│   ├── synthetic_generator.py
│   ├── metrics.py
│   ├── benchmark.py
│   └── run_eval.py
├── web/                    # Web interface
└── docs/                   # Documentation
```

## License

MIT
