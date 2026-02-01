# Command Reference

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
python -m eval.generate_dataset 50                        # Generate QA dataset

# Retrieval evaluation
python -m eval.eval_retrieval                             # Evaluate retrieval quality

# Routing evaluation
python -m eval.eval_routing                               # Evaluate binary routing system
python -m eval.eval_routing --type simple_fact            # Test specific query types
python -m eval.eval_routing --html                        # Generate HTML report
python -m eval.eval_routing --trials 10                   # Limit test queries

# Generation quality evaluation (single-chunk)
python -m eval.eval_generation qwen3:latest mistral       # Compare models (Ollama)
python -m eval.eval_generation --provider mlx model1      # Use MLX provider
python -m eval.eval_generation model1 model2 --trials 10  # Multiple trial runs
python -m eval.eval_generation --html model1 model2       # With HTML report

# Multi-chunk generation evaluation
python -m eval.generate_multichunk_dataset                # Generate multi-chunk dataset
python -m eval.generate_multichunk_dataset --size 50      # Custom dataset size
python -m eval.eval_generation_multichunk qwen3:latest    # Evaluate model(s)
python -m eval.eval_generation_multichunk --trials 10     # Limit questions
python -m eval.eval_generation_multichunk --html model1   # With HTML report
python -m eval.eval_generation_multichunk --generate-dataset  # Alternative dataset generation

# Summary evaluation
python -m eval.evaluate_summaries                         # Default (Ollama)
python -m eval.evaluate_summaries --provider mlx          # Use MLX provider
python -m eval.evaluate_summaries --html                  # Generate HTML report

# Dashboard
python -m eval.model_dashboard                            # Multi-model comparison dashboard
```

## Utility Scripts

Scripts located in `scripts/` to help with data analysis and debugging.

```bash
# Check enrichment (summarization/HyDE) status of conversations
python scripts/check_enrichment_status.py                  # Summary of all conversations
python scripts/check_enrichment_status.py --detailed       # Per-conversation breakdown
python scripts/check_enrichment_status.py --show-enriched  # List fully enriched conversations
python scripts/check_enrichment_status.py --show-not-enriched # List conversations not started

# Get conversation statistics
python scripts/conversation_stats.py                       # List all conversations by message count
python scripts/conversation_stats.py --limit 10            # Top 10 conversations
python scripts/conversation_stats.py --min-messages 100    # Filter small conversations
python scripts/conversation_stats.py --json                # JSON output for external tools
```
