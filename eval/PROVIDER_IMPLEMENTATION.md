# LLM Provider Abstraction Implementation

## Overview

This implementation adds a provider abstraction layer to the evaluation system, enabling support for both Ollama and MLX providers, and generates per-model JSON reports instead of single aggregated files.

## Changes Made

### 1. New File: `eval/llm_provider.py`

Created a provider abstraction with:
- `LLMProvider`: Abstract base class defining the interface
- `OllamaProvider`: HTTP API wrapper for Ollama
- `MLXProviderWrapper`: Wrapper for the existing MLX provider
- `create_provider()`: Factory function for provider instantiation

**Interface:**
```python
def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
    """Generate text from chat messages."""
```

### 2. Modified: `eval/eval_generation.py`

**Key Changes:**
- Added `--provider` CLI argument (choices: "ollama", "mlx")
- Replaced direct `requests.post()` calls with provider abstraction
- Created `generate_per_model_json()` function for per-model JSON reports
- Updated `generate_json_report()` to accept provider parameter
- Modified model availability check to skip Ollama check when using MLX
- Providers are instantiated once and reused for all evaluations

**New Report Structure:**
- Per-model JSON files: `{model_name}_{trials}trials_{provider}_{timestamp}.json`
- Each per-model JSON includes metadata, summary metrics, trials, and QA pairs
- No aggregated JSON files - each model gets its own report

### 3. Modified: `eval/evaluate_summaries.py`

**Key Changes:**
- Added `--provider` CLI argument
- Updated `SummaryEvaluator.__init__()` to accept `provider_type` parameter
- Replaced `_call_llm()` direct Ollama calls with provider abstraction
- Provider is instantiated once in constructor and reused

### 4. Modified: `eval/metrics.py`

**Key Changes:**
- Updated `RAGASMetrics.__init__()` to accept `provider_type` parameter
- Modified `_llm_judge()` to use provider abstraction with lazy initialization
- Removed direct `requests.post()` calls to Ollama API

### 5. Modified: `docs/COMMANDS.md`

Updated evaluation commands section with:
- Provider flag examples for both Ollama and MLX
- Reorganized commands by category
- Added inline comments for clarity

### 6. Test File: `eval/test_provider.py`

Created test script to verify:
- Provider creation for both Ollama and MLX
- Interface consistency across providers
- Basic generation functionality (when Ollama is available)

## Usage Examples

### Generation Evaluation with Ollama (default)
```bash
python -m eval.eval_generation qwen3:latest mistral --trials 5
```

### Generation Evaluation with MLX
```bash
python -m eval.eval_generation --provider mlx \
    mlx-community/Ministral-3-8B-Instruct-2512-4bit \
    mlx-community/Qwen-2.5-3B-Instruct-4bit \
    --trials 5
```

### Summary Evaluation with MLX
```bash
python -m eval.evaluate_summaries --provider mlx --html
```

## Per-Model JSON Report Format

Each model gets its own JSON file with the following structure:

```json
{
  "metadata": {
    "timestamp": "2026-02-01T14:30:22.123456",
    "model": "qwen3:latest",
    "provider": "ollama",
    "judge_model": "qwen3:latest",
    "num_trials": 5,
    "num_questions": 5
  },
  "summary": {
    "avg_faithfulness": 0.823,
    "avg_relevance": 0.891,
    "avg_speed_wps": 42.15
  },
  "trials": [
    {
      "answer": "...",
      "time": 2.34,
      "words_per_sec": 42.3,
      "faith": {"score": 0.8, "explanation": "..."},
      "relev": {"score": 0.9, "explanation": "..."}
    }
  ],
  "qa_pairs": [...]
}
```

## Benefits

1. **Provider Flexibility**: Easy to switch between Ollama and MLX or add new providers
2. **Speed Optimization**: MLX can leverage Apple Silicon for faster inference
3. **Better Organization**: Per-model JSON files are easier to compare and track
4. **Cleaner Code**: Provider abstraction eliminates duplicate HTTP calls
5. **Type Safety**: Unified interface enforced by abstract base class

## Migration Notes

### For Users
- **Breaking change**: JSON report format changed from aggregated to per-model files
- Old aggregated JSON files are no longer generated
- Add `--provider mlx` to use MLX instead of Ollama
- Per-model JSON files are generated automatically with format: `{model}_{trials}trials_{provider}_{timestamp}.json`

### For Developers
- Import providers via `from eval.llm_provider import create_provider`
- Use `provider.generate(messages, **kwargs)` instead of direct HTTP calls
- Pass `provider_type` parameter to evaluation classes
- Update any scripts that expected aggregated JSON format

## Future Enhancements

Potential improvements (not implemented):
1. Async MLX batching for parallel query processing
2. Mixed providers (different provider for test vs judge)
3. Provider auto-detection based on availability
4. JSON aggregation script for merging per-model files
5. HTML reports with client-side JSON loading for dynamic updates

## Testing

Run the provider test suite:
```bash
python eval/test_provider.py
```

Expected output:
- ✅ Ollama Provider creation and basic generation
- ✅ MLX Provider creation
- ✅ Interface consistency verification
