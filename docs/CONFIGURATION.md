# Environment Configuration

This project now uses an environment variable-based configuration system to avoid hardcoded paths in the code.

## Quick Setup

### Option 1: Interactive Script (Recommended)

python scripts/setup/setup_env.py
```

The script will guide you through configuring all necessary settings.

### Option 2: Manual Copy

```bash
# 1. Copy the template
cp .env.example .env

# 2. Edit with your paths
nano .env  # or vim, code, etc.
```

## Hardware & Memory Optimization

### Apple Silicon (M1/M2/M3)
If you are running on a Mac with unified memory (e.g., M1 Pro with 16GB RAM), the `BAAI/bge-m3` model can trigger **MPS out-of-memory** errors due to its large context and the way PyTorch manages the shared memory pool.

**Recommended settings for 16GB RAM:**
- **Batch Size:** Use `--batch-size 10` (or lower) for `setup_embeddings.py`.
- **Force CPU:** If crashes persist even with small batches, use the `--cpu` flag. CPU embedding is slower but more stable on limited RAM as it can use system swap.
- **Memory Watermark:** If you want to push MPS limits, you can try setting `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0` in your environment, but this may cause system instability.

Example command for stable embedding on M1 Pro 16GB:
```bash
.venv/bin/python3 setup_embeddings.py --enriched-only --batch-size 10
```

## Environment Variables

### Essential Paths

| Variable | Description | Example |
|----------|-------------|---------|
| `INSTAGRAM_EXPORT_DIR` | Directory of your Instagram export (inbox) | `~/Documents/instagram/messages/inbox` |
| `BASE_DIR` | Project root directory (auto-detected) | `/Users/username/instagram-assistant` |
| `CONVERSATIONS_DIR` | Directory for converted conversations | `instagram_conversations` (relative) |
| `INDEX_DIR` | Directory for RAG indexes | `rag_data` (relative) |

### User Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `USER_NAME` | Your first name | `Ismaël` |

### LLM Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_MODEL` | Ollama model | `qwen3:latest` |
| `OLLAMA_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_ENDPOINTS` | Multiple Ollama endpoints (comma-separated) | Uses `OLLAMA_URL` |
| `USE_LOAD_BALANCING` | Enable load balancing across endpoints | `false` |

#### Multi-Endpoint Setup (Distributed Processing)

To parallelize LLM work across multiple machines:

```bash
# In .env
OLLAMA_ENDPOINTS=http://localhost:11434,http://192.168.1.16:11434
USE_LOAD_BALANCING=true
```

On the remote machine, ensure Ollama is listening on all interfaces:
```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

The system will automatically load-balance requests across all healthy endpoints.

### Embeddings Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `EMBEDDING_MODEL` | Embeddings model | `BAAI/bge-m3` |
| `USE_GPU` | Use GPU if available | `true` |

### RAG Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `TOP_K` | Number of chunks retrieved (fallback) | `12` |
| `MIN_SIMILARITY` | Minimum similarity score | `0.3` |
| `USE_RERANKING` | Enable reranking | `true` |
| `USE_HYBRID` | Enable hybrid search | `true` |

**Note:** The `top_k` value is dynamically set per intent by `query_analyzer.py` (specific_fact: 15, broad_summary: 40, complex_reasoning: 30). These values are optimized from statistical analysis of 32k chunks. See [TOP_K_ANALYSIS_REPORT.md](TOP_K_ANALYSIS_REPORT.md) for details.

### Chunking Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CHUNK_MAX_MESSAGES` | Max messages per chunk | `50` |
| `CHUNK_MAX_DAYS` | Max duration of a chunk (days) | `3` |
| `CHUNK_OVERLAP` | Overlap between chunks | `5` |

## Analysis Tools and Statistics

The project now includes analysis tools:

| Script | Description |
|--------|-------------|
| `python utils/rag_stats.py` | Detailed statistical analysis (conversations, messages, chunks) |
| `python utils/top_20_messages.py` | Displays the 20 largest conversations |
| `python analyze_chunks_stats.py` | Chunk size analysis and top_k optimization recommendations |

For detailed chunk analysis and top_k configuration guidance, see [TOP_K_ANALYSIS_REPORT.md](TOP_K_ANALYSIS_REPORT.md).

## Advanced Indexing Scripts

### setup_rag_batch.py

The main indexing script supports new flags:

| Flag | Description |
|------|-------------|
| `--limit N` | Limit indexing to the first N conversations (useful for quick testing) |
| `--import-test` | Automatically import the test dataset from `test_conversations/` |
| `--reset` | Delete the entire index and start from scratch |
| `--status` | Display the current status of indexing |

Example:
```bash
# Import test data and index only 5 conversations
python setup_rag_batch.py --import-test --limit 5 --reset
```

## Complete Workflow

### First Use

```bash
# 1. Configure the environment
python scripts/setup/setup_env.py
# 2. Install dependencies (includes python-dotenv)
pip install -r requirements.txt

python scripts/ingestion/instagram_to_text.py

# 4. Create the index
python setup_rag_batch.py

# 5. Launch the app
python app.py
```

### Merging Multiple Exports

If you have multiple Instagram exports (old + new):

```bash
# 1. Merge exports
python merge_instagram_exports.py \
    ~/Documents/export_june_2024/messages/inbox \
    ~/Documents/export_dec_2024/messages/inbox \
    -o ~/Documents/instagram_merged/messages/inbox

# 2. Update your .env
# Change INSTAGRAM_EXPORT_DIR to the merged directory
nano .env

# 3. Convert and index
python scripts/maintenance/update_index.py
```

### Update with a New Export

```bash
# 1. Merge with the old export
python merge_instagram_exports.py \
    ~/Documents/instagram_merged/messages/inbox \
    ~/Documents/new_export/messages/inbox \
    -o ~/Documents/instagram_merged_v2/messages/inbox

# 2. Update INSTAGRAM_EXPORT_DIR in .env

# 3. Reconvert and update the index
python scripts/ingestion/instagram_to_text.py
python scripts/maintenance/update_index.py
```

## Relative vs Absolute Paths

- **Relative Paths**: If you specify a simple name (e.g., `instagram_conversations`), it will be relative to `BASE_DIR`
- **Absolute Paths**: Start with `/` (Unix) or `C:\` (Windows), used as is

Examples:
```bash
# Relative to project
CONVERSATIONS_DIR=instagram_conversations
# → /Users/username/project/instagram_conversations

# Absolute
CONVERSATIONS_DIR=/Users/username/custom/location
# → /Users/username/custom/location
```

## Security

The `.env` file contains your personal paths and **must never be committed to Git**.

It is already in `.gitignore`:
```
# Environment Variables
.env
.env.local
.env.*.local
```

## Troubleshooting

### Script cannot find my conversations

Check that `INSTAGRAM_EXPORT_DIR` points to the correct directory:
```bash
ls "$INSTAGRAM_EXPORT_DIR"
# Should list your conversation directories
```

### Environment variables not loaded

Make sure `python-dotenv` is installed:
```bash
pip install python-dotenv
```

### Error "module 'dotenv' not found"

```bash
pip install --upgrade python-dotenv
```

## Automatic Import Logic

The script `scripts/ingestion/instagram_to_text.py` has been improved to automatically detect your Instagram exports. It searches in the following priority order:

1. The `INSTAGRAM_EXPORT_DIR` environment variable (if defined)
2. The `merged_instagram_export/` directory (created by `merge_instagram_exports.py`)
3. Folders in `original_import_folders/`
4. Any folder starting with `instagram-` in the root

This logic allows easily handling multiple or merged exports without constant reconfiguration.

## Migration from Old Version

If you are using a previous version with hardcoded paths:

1. Run `python scripts/setup/setup_env.py`
2. Your existing data in `instagram_conversations/` and `rag_data/` will be automatically used
3. No re-indexing is necessary

The default paths correspond to the old hardcoded locations.