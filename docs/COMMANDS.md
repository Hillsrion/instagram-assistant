# Command Reference

## Backend

```bash
python3 app.py                    # Start FastAPI server on port 8000
python3 cli.py                    # Interactive CLI chat
python3 cli.py --prompt "query"   # Single query mode
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
python3 setup_rag.py              # Run full pipeline
python3 setup_rag.py --status     # Show indexing progress
python3 setup_rag.py --reset      # Full reindex from scratch
python3 setup_rag.py --only chunks  # Run a single step (chunks, embeddings, etc.)
python3 instagram_to_text.py      # Convert JSON export to text
python3 update_index.py           # Incremental update
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

# Generation quality evaluation
python -m eval.eval_generation qwen3:latest mistral       # Compare models (Ollama)
python -m eval.eval_generation --provider mlx model1      # Use MLX provider
python -m eval.eval_generation model1 model2 --trials 10  # Multiple trial runs
python -m eval.eval_generation --html model1 model2       # With HTML report

# Summary evaluation
python -m eval.evaluate_summaries                         # Default (Ollama)
python -m eval.evaluate_summaries --provider mlx          # Use MLX provider
python -m eval.evaluate_summaries --html                  # Generate HTML report

# Dashboard
python -m eval.model_dashboard                            # Multi-model comparison dashboard
```
