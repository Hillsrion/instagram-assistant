# Instagram Assistant Documentation

Welcome to the Instagram Assistant documentation, a production-ready RAG (Retrieval-Augmented Generation) system for analyzing Instagram conversations.

## Documentation Index

| Document | Description |
|----------|-------------|
| [Quick Start Guide](QUICKSTART.md) | Installation and first steps |
| [Features Documentation](FEATURES.md) | Comprehensive feature guide |
| [API Reference](API.md) | REST endpoints and SSE events |
| [Evaluation Guide](EVAL.md) | Dataset generation, benchmarks, and metrics |
| [Configuration](CONFIGURATION.md) | Configuration options |

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Instagram Assistant                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ React App    │    │     CLI      │    │     API      │       │
│  │ (frontend/)  │    │   (cli.py)   │    │   (app.py)   │       │
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

### 1. LLM Enrichment
- Semantic metadata generation via local LLM
- 5 enriched fields: narrative summary, hypothetical questions, speaker intents, temporal context, emotions
- Emotion analysis (dominant emotion, tone, tension level)
- Dramatically improves retrieval quality

### 2. Hybrid Search
- Dense search (FAISS embeddings)
- Lexical search (BM25)
- Cross-encoder reranking
- Context expansion with adjacent chunks

### 3. Robustness
- Configurable confidence thresholds
- Automatic PII filtering (7 types detected)
- Anti-hallucination prompts
- Strict source citation requirements

### 4. Incremental Updates
- Automatic change detection (SHA256 hashing)
- Partial indexing (add/modify/delete)
- Persistent state tracking
- No full reindex needed

### 5. Automated Evaluation
- Synthetic QA pair generation
- RAGAS metrics (Accuracy, MRR, Faithfulness, Relevance)
- Configuration comparison
- Benchmark reports

### 6. Enhanced UX
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
| Frontend | React 19, Vite, TanStack Router, Tailwind CSS v4 |

## Getting Started

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Index conversations**: `python setup_rag_batch.py`
3. **Launch API**: `python app.py`
4. **Launch Frontend**:
   ```bash
   cd frontend
   pnpm install && pnpm dev --open
   ```

## Project Structure

```
instagram-assistant/
├── app.py                  # FastAPI server
├── cli.py                  # CLI interface
├── frontend/               # React web application
│   ├── src/                # Frontend source code
│   └── package.json        # Frontend dependencies
├── setup_rag_batch.py      # Initial indexing
├── update_index.py         # Incremental updates
├── rag_pipeline/           # Core RAG components
│   ├── config.py
│   ├── chunker.py
│   ├── enricher.py         # LLM enrichment
│   ├── embeddings.py
│   ├── vector_store.py
│   ├── reranker.py         # Cross-encoder reranking
│   ├── advanced_retriever.py
│   ├── chat.py
│   ├── pii_filter.py
│   └── delta_tracker.py
├── eval/                   # Evaluation pipeline
│   ├── generate_dataset.py # Generate QA pairs
│   ├── eval_retrieval.py   # Evaluate retrieval quality
│   ├── eval_generation.py  # Evaluate LLM generation quality
│   ├── compare_configs.py  # Compare RAG configurations
│   ├── synthetic_generator.py  # QA pair generation (lib)
│   ├── metrics.py          # RAGAS metrics (lib)
│   └── benchmark.py        # Benchmark runner (lib)
├── web/                    # Web interface
└── docs/                   # Documentation
```

## License

MIT
