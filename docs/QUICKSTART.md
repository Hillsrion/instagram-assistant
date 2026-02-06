# Instagram Assistant - Quick Start Guide

> For a detailed explanation of each pipeline stage, see [RAG_PIPELINE.md](RAG_PIPELINE.md).

## Prerequisites

- Python 3.10+
- Ollama with a model installed (e.g., `qwen3:latest`)
- Instagram conversation files in `.txt` format

## Installation

```bash
# Clone the project
git clone <repo-url>
cd instagram-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Edit `rag_pipeline/config.py` if needed:

```python
# Paths
base_dir: Path = Path(__file__).parent.parent

# LLM model (Ollama)
llm_model: str = "qwen3:latest"
ollama_url: str = "http://localhost:11434"

# Your name (to identify your messages)
user_name: str = "YourName"

# Confidence threshold (0.25 = 25%)
confidence_threshold: float = 0.25

# Enable PII filtering
enable_pii_filter: bool = True
```

## Data Pipeline & Initial Indexing

The system requires two steps to process your data:
1. **Conversion**: Instagram JSON export -> Text files
2. **Indexing**: Text files -> RAG Vector Index

### 1. Prepare your Instagram Export

1. Request your data export from Instagram (JSON format).
2. Download and unzip the export.
3. Configure the path in `.env` (or use `scripts/setup/setup_env.py`):

```bash
INSTAGRAM_EXPORT_DIR=/path/to/your/instagram_export/messages/inbox
```

*Note: You can also simply place your `inbox` folder inside `merged_instagram_export/` in the project root.*

### 2. Convert to Text

Run the conversion script to parse JSON files and generate optimized text files:

```bash
python scripts/ingestion/instagram_to_text.py
```

This will populate `instagram_conversations/` with `.txt` files.

### 3. Run Indexing

Build the RAG index from the text files:

```bash
python setup_rag_batch.py
```

This will:
1. Split conversations into chunks
2. Enrich chunks with summaries and hypothetical questions (via LLM)
3. Generate embeddings
4. Build FAISS, BM25, and metadata indexes

**Duration**: ~1-2 minutes for 50 conversations depending on your hardware.

## Usage

### Web Interface

```bash
python app.py
```

Open http://localhost:8000 in your browser.

### CLI Interface

```bash
python cli.py
```

Type your questions directly in the terminal.

### Incremental Updates

After adding/modifying files:

```bash
python scripts/maintenance/update_index.py --status

# Apply changes
python scripts/maintenance/update_index.py```

## Evaluation

### Generate Test Dataset

```bash
python -m eval.dataset.generate_dataset 50
```

### Run Benchmark (Retrieval)

```bash
python -m eval.retrieval.eval_retrieval
```

### Compare Configurations

```bash
python -m eval.config_comparison.compare_configs
```

## Useful Commands

| Command | Description |
|---------|-------------|
| `python app.py` | Launch web server |
| `python cli.py` | Command-line interface |
| `python setup_rag_batch.py` | Full indexing |
| `python scripts/maintenance/update_index.py` | Incremental update |
| `python scripts/maintenance/update_index.py --status` | View changes |
| `python scripts/maintenance/update_index.py --full` | Force full rebuild |
| `python utils/rag_stats.py` | View dataset statistics |
| `python utils/top_20_messages.py` | List top conversations by size |
| `python -m eval.dataset.generate_dataset N` | Generate N QA pairs |
| `python -m eval.retrieval.eval_retrieval` | Run retrieval benchmark |
| `python -m eval.generation.eval_generation <models>` | Compare LLM generation |
| `python -m eval.config_comparison.compare_configs` | Compare RAG configurations |

## Data Structure

```
rag_data/
├── faiss_index/
│   ├── index.faiss      # Vector index
│   └── chunks.json      # Chunk metadata
├── bm25_index.pkl       # BM25 index
├── metadata.db          # SQLite metadata
├── file_state.json      # File state (delta tracker)
├── enrichment_state.json # Enrichment state
├── eval_dataset.json    # Evaluation dataset
└── conversations.json   # Web conversation history
```

## Troubleshooting

### "FAISS index not found"

Run initial indexing:
```bash
python setup_rag_batch.py
```

### "Cannot connect to Ollama"

Check that Ollama is running:
```bash
ollama serve
```

### Poor quality responses

1. Increase `top_k` in config
2. Check that confidence threshold isn't too high
3. Re-run chunk enrichment

### Incremental update doesn't detect changes

Changes are detected by content hash. If only the file date changed, it won't be considered modified.

To force update:
```bash
python scripts/maintenance/update_index.py --full
```

## Resources

- [Features Documentation](FEATURES.md)
- [API Reference](API.md)
