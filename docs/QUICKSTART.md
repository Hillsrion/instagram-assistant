# Instagram Assistant - Quick Start Guide

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

## Initial Indexing

### 1. Prepare Conversations

Place your `.txt` files in `instagram_conversations/`.

Expected format:
```
# Instagram Conversation with Alice
ID: conversation_123
Participants: YourName, Alice
============================================================

[2024-01-15 10:00:00] Alice: Hi!
[2024-01-15 10:01:00] YourName: Hey, how are you?
...
```

### 2. Run Indexing

```bash
python setup_rag_batch.py
```

This will:
1. Split conversations into chunks
2. Enrich chunks with summaries and hypothetical questions
3. Generate embeddings
4. Build FAISS, BM25, and metadata indexes

**Duration**: ~1-2 minutes for 50 conversations

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
# View detected changes
python update_index.py --status

# Apply changes
python update_index.py
```

## Evaluation

### Generate Test Dataset

```bash
python -m eval.run_eval --generate 50
```

### Run Benchmark

```bash
python -m eval.run_eval --benchmark
```

### Compare Configurations

```bash
python -m eval.run_eval --compare
```

## Useful Commands

| Command | Description |
|---------|-------------|
| `python app.py` | Launch web server |
| `python cli.py` | Command-line interface |
| `python setup_rag_batch.py` | Full indexing |
| `python update_index.py` | Incremental update |
| `python update_index.py --status` | View changes |
| `python update_index.py --full` | Force full rebuild |
| `python -m eval.run_eval --generate N` | Generate N QA pairs |
| `python -m eval.run_eval --benchmark` | Run benchmark |
| `python -m eval.run_eval --compare` | Compare configs |

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
python update_index.py --full
```

## Resources

- [Features Documentation](FEATURES.md)
- [API Reference](API.md)
