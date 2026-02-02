# Command Reference

### Initial Setup

```bash
# 1. Create a dedicated virtual environment (Recommended)
python3 -m venv .venv

# 2. Activate and install
source .venv/bin/activate
pip install -r requirements.txt

# Alternative: use the Makefile
make install
```

### ⚠️ Important: MLX Environment Issues
If you encounter errors like `ValueError: Tokenizer class TokenizersBackend does not exist` or library version conflicts with MLX, **ensure you are using the project's virtual environment (`.venv`)**. Global Python environments often have conflicting `transformers` versions.

To fix environment issues:
1. Delete the existing environment: `rm -rf .venv`
2. Re-install: `make install`
3. Always run commands through `make` or with the `.venv` activated.

## Quick Access (Recommended)

The project includes a `Makefile` that handles virtual environment activation automatically.

```bash
make install       # Setup environment
make run           # Start backend
make cli           # Start CLI
make index         # Run RAG indexing
make status        # Check status
```

## Manual Commands (Backend)

```bash
python app.py                    # Start FastAPI server on port 8000
python cli.py                    # Interactive CLI chat
python cli.py --prompt "query"   # Single query mode
```

## Frontend

```bash
cd frontend && pnpm install       # Install dependencies
cd frontend && pnpm dev           # Start dev server on port 5173
cd frontend && pnpm build         # Production build
cd frontend && pnpm lint          # Run ESLint
```

## Indexing Pipeline

```bash
python setup_rag.py              # Run full pipeline
python setup_rag.py --status     # Show indexing progress
python setup_rag.py --reset      # Full reindex from scratch
python setup_rag.py --only chunks  # Run a single step (chunks, embeddings, etc.)
python instagram_to_text.py      # Convert JSON export to text
python update_index.py           # Incremental update
```

## Testing

```bash
pytest tests/                     # Run all unit tests
pytest tests/test_config.py       # Run single test file
pytest tests/api/                 # Run API tests only
pytest tests/setup/               # Run setup script tests
```

## Evaluation

```bash
# Dataset generation
python -m eval.dataset.generate_dataset 50                           # Generate QA dataset
python -m eval.dataset.generate_multichunk_dataset --size 50         # Multi-chunk dataset

# Retrieval evaluation
python -m eval.retrieval.eval_retrieval                              # Evaluate retrieval quality

# Routing evaluation
python -m eval.routing.eval_routing                                  # Evaluate binary routing system
python -m eval.routing.eval_routing --type simple_fact               # Test specific query types
python -m eval.routing.eval_routing --html                           # Generate HTML report
python -m eval.routing.eval_routing --trials 10                      # Limit test queries

# Generation quality evaluation (single-chunk)
python -m eval.generation.eval_generation qwen3:latest mistral       # Compare models (Ollama)
python -m eval.generation.eval_generation --provider mlx model1      # Use MLX provider
python -m eval.generation.eval_generation model1 model2 --trials 10  # Multiple trial runs
python -m eval.generation.eval_generation --html model1 model2       # With HTML report

# Multi-chunk generation evaluation
python -m eval.generation.eval_generation_multichunk qwen3:latest    # Evaluate model(s)
python -m eval.generation.eval_generation_multichunk --trials 10     # Limit questions
python -m eval.generation.eval_generation_multichunk --html model1   # With HTML report

# Summary evaluation
python -m eval.summaries.evaluate_summaries                          # Default (Ollama)
python -m eval.summaries.evaluate_summaries --provider mlx           # Use MLX provider
python -m eval.summaries.evaluate_summaries --html                   # Generate HTML report

# Configuration comparison
python -m eval.config_comparison.compare_configs                     # Compare RAG configs

# Enrichment validation
python -m eval.enrichment.validate_enrichment --sample --size 20     # Validate enrichment quality
python -m eval.enrichment.validate_enrichment --enrich --model mistral-8b  # Enrich & validate

# Dashboard
python -m eval.generation.model_dashboard                            # Multi-model comparison dashboard
```

## Distributed Enrichment (Multiple Machines)

To speed up enrichment across multiple machines:

**On Machine 1:**
```bash
python setup_enrich.py --total-shards 2 --shard-index 0
# Processes chunks 0, 2, 4, 6... (~50% of work)
# Output: rag_data/chunks_shard0.json
```

**On Machine 2:**
```bash
# First, copy chunks.json from Machine 1
scp user@machine1:~/instagram-assistant/rag_data/chunks.json ./rag_data/

python setup_enrich.py --total-shards 2 --shard-index 1
# Processes chunks 1, 3, 5, 7... (~50% of work)
# Output: rag_data/chunks_shard1.json
```

**After both complete:**
```bash
# Copy shard files to one machine
scp user@machine2:~/instagram-assistant/rag_data/chunks_shard1.json ./rag_data/

# Merge shards
python scripts/merge_enriched_shards.py

# Continue pipeline
python setup_embeddings.py
```

Monitor distributed progress:
```bash
python scripts/check_enrichment_status.py --show-shards  # Show shard file status
tail -f enrichment_shard0.log  # On Machine 1
tail -f enrichment_shard1.log  # On Machine 2
```

## Utility Scripts

Scripts located in `scripts/` to help with data analysis and debugging.

```bash
# Check enrichment (summarization/HyDE) status of conversations
python scripts/check_enrichment_status.py                  # Summary of all conversations
python scripts/check_enrichment_status.py --detailed       # Per-conversation breakdown
python scripts/check_enrichment_status.py --show-enriched  # List fully enriched conversations
python scripts/check_enrichment_status.py --show-not-enriched # List conversations not started
python scripts/check_enrichment_status.py --show-shards    # Show progress on shard files during distributed enrichment

# Merge enriched shards (after distributed enrichment)
python scripts/merge_enriched_shards.py                    # Auto-detect and merge all shards
python scripts/merge_enriched_shards.py --dry-run          # Preview merge without writing
python scripts/merge_enriched_shards.py --verbose          # Show detailed merge progress

# Get conversation statistics
python scripts/conversation_stats.py                       # List all conversations by message count
python scripts/conversation_stats.py --limit 10            # Top 10 conversations
python scripts/conversation_stats.py --min-messages 100    # Filter small conversations
python scripts/conversation_stats.py --json                # JSON output for external tools

# Analyze chunks for top_k optimization
python analyze_chunks_stats.py                             # Analyze all chunks, display stats
python analyze_chunks_stats.py --output report.md          # Generate markdown report
python analyze_chunks_stats.py --chunks path/to/chunks.json # Custom chunks path
# See docs/TOP_K_ANALYSIS_REPORT.md for detailed analysis and recommendations
```
