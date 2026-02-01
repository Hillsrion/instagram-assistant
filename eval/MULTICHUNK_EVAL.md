# Multi-Chunk Generation Evaluation

## Overview

The multi-chunk evaluation system tests LLM generation quality with **multiple conversation chunks** as context, reflecting real-world usage where 5-25 chunks are typically provided based on query intent.

This extends `eval_generation.py` (single-chunk eval) with:
- **Multi-chunk context**: All chunks from `source_chunk_ids`, not just the first
- **Production formatting**: Exact replication of `advanced_retriever._format_context()`
- **Advanced metrics**: Attribution (correct chunk usage) + Cross-Chunk Coherence (synthesis quality)
- **Intent-based scenarios**: 5 chunks (factual), 10 (complex), 15 (summary)

## Quick Start

### 1. Generate Multi-Chunk Dataset

```bash
# Generate 30 QA pairs requiring multiple chunks
python -m eval.generate_multichunk_dataset --size 30

# Custom chunk counts
python -m eval.generate_multichunk_dataset --size 50 --chunks 5,10,15
```

This creates `eval/eval_dataset_multichunk.json` with questions categorized by intent:
- **specific_fact** (5 chunks): Cross-reference questions
- **complex_reasoning** (10 chunks): Multi-step reasoning
- **broad_summary** (15 chunks): Comprehensive synthesis

### 2. Run Evaluation

```bash
# Evaluate a single model
python -m eval.eval_generation_multichunk qwen3:latest --trials 10

# Compare multiple models
python -m eval.eval_generation_multichunk qwen3:latest mistral:latest --trials 20

# Generate HTML report with visualizations
python -m eval.eval_generation_multichunk qwen3:latest --trials 10 --html

# Use MLX provider instead of Ollama
python -m eval.eval_generation_multichunk --provider mlx qwen3:latest --trials 10
```

### 3. View Results

**JSON reports** are saved to:
```
eval/results/eval_generation_multichunk/
├── qwen3-latest_10trials_ollama_20260201_171554.json
└── mistral-latest_10trials_ollama_20260201_171554.json
```

**HTML report** (with `--html` flag):
```
eval/results/eval_generation_multichunk/
└── multichunk_10trials_qwen3-latest_vs_mistral-latest_20260201_171554.html
```

## Metrics

### Core Metrics (Compatible with Single-Chunk Eval)

1. **Faithfulness** (0-1): Answer fidelity to source chunks
   - Uses LLM-as-judge to verify no hallucinations
   - Checks factual accuracy against provided context

2. **Relevance** (0-1): How well answer addresses the question
   - Compares generated answer to expected answer
   - Evaluates completeness and directness

### Multi-Chunk Specific Metrics

3. **Chunk Attribution** (0-1): Correct chunk usage
   - Did the LLM cite/use the expected source chunks?
   - Are information sources traceable to correct chunks?
   - Penalizes hallucination from non-provided chunks

4. **Cross-Chunk Coherence** (0-1): Synthesis quality
   - Logical combination of information across chunks
   - Absence of contradictions or inconsistencies
   - Fluency and coherence of multi-chunk synthesis

### Performance Metrics

5. **Generation Time**: Seconds to generate answer
6. **Words per Second**: Throughput metric

## Architecture

### Key Files

```
eval/
├── eval_generation_multichunk.py      # Main evaluation script
├── generate_multichunk_dataset.py     # Dataset generation CLI
├── eval_dataset_multichunk.json       # Generated multi-chunk dataset
├── synthetic_generator.py             # Updated with MultiChunkQAPair
├── metrics.py                         # Updated with attribution/coherence metrics
└── _output_paths.py                   # Updated with multichunk report paths
```

### Data Structures

#### MultiChunkQAPair (extends QAPair)

```python
@dataclass
class MultiChunkQAPair(QAPair):
    intent: str                           # "specific_fact", "complex_reasoning", "broad_summary"
    expected_chunk_attribution: List[str] # Chunks that should be cited
    cross_chunk_required: bool            # Whether synthesis is needed
```

#### MultiChunkEvalResult

```python
@dataclass
class MultiChunkEvalResult:
    question: str
    expected_answer: str
    generated_answer: str
    source_chunk_ids: List[str]
    intent: str

    # Core metrics
    faithfulness: Dict[str, Any]          # {score, explanation}
    relevance: Dict[str, Any]

    # Multi-chunk metrics
    chunk_attribution_score: float
    chunk_attribution_explanation: str
    cross_chunk_coherence: float
    cross_chunk_explanation: str

    # Performance
    num_chunks_provided: int
    generation_time: float
    words_per_sec: float
```

### Context Formatting

The evaluation **exactly replicates** production formatting from `advanced_retriever._format_context()`:

```python
def format_multichunk_context(chunks: List[Chunk], ...) -> str:
    """
    Format:
    === DOCUMENT 1 ===
    Source: {file}
    Participants: {participants}
    Period: {date_start} → {date_end}
    Score: {score:.2f}
    ---
    {content}

    === DOCUMENT 2 ===
    ...
    """
```

This ensures evaluation results reflect real-world performance.

## Dataset Generation Process

### Chunk Grouping

1. **By participants**: Group chunks by participant combination
2. **By timeframe**: Further group by temporal proximity (same conversation file)
3. **Filter**: Keep groups with 3+ chunks

### LLM-Based Question Generation

For each chunk group:

1. **Select N chunks** based on intent (5, 10, or 15)
2. **Prompt LLM** to generate a question requiring multi-chunk synthesis:
   ```
   Types:
   - Cross-reference: "How did X's opinion on Y change over time?"
   - Synthesis: "Summarize all discussions about Z"
   - Attribution: "Who said what about X?"
   ```
3. **Extract**:
   - Question
   - Expected answer (synthesis of relevant info)
   - Source chunk IDs
   - Expected attribution (which chunks contain critical info)

### Validation

- Questions must genuinely need multiple chunks (enforced by prompt)
- Distribution across intents is balanced
- Each question has 5-15 source chunks

## HTML Report Features

### Visualizations

1. **Summary Cards**: Per-model metric overview
2. **Core Metrics Chart**: Faithfulness + Relevance comparison
3. **Multi-Chunk Metrics Chart**: Attribution + Coherence comparison
4. **Performance by Chunk Count**: How metrics change with more chunks

### Question Details

For each question:
- **Header**: Question, intent, number of chunks
- **Expandable source chunks**: All chunks provided as context
- **Model responses**: Side-by-side comparison
- **Metric badges**: Color-coded scores (green/yellow/red)
- **Judge explanations**: Attribution and coherence assessments

### Attribution Heatmap (Future)

- Matrix: Questions × Chunks
- Color: Used (green) vs Ignored (gray) vs Hallucination (red)

## Comparison with eval_generation.py

| Feature | eval_generation.py | eval_generation_multichunk.py |
|---------|-------------------|------------------------------|
| Context | Single chunk (first in list) | All chunks from source_chunk_ids |
| Formatting | Basic content only | Production headers + metadata |
| Metrics | Faithfulness, Relevance | + Attribution, Cross-Chunk Coherence |
| Scenarios | Generic | Intent-based (5/10/15 chunks) |
| Use Case | Isolate generation quality | Test real-world multi-chunk synthesis |

## Intent Mapping (Production Alignment)

Based on `query_analyzer.py:172-191`:

| Intent | Chunk Count | Question Type | Example |
|--------|-------------|--------------|---------|
| specific_fact | 5 | Cross-reference | "How did X evolve?" |
| complex_reasoning | 10 | Multi-step | "What themes emerged in Y?" |
| broad_summary | 15 | Synthesis | "Summarize all discussions about Z" |

## Validation Tests

### Implemented

1. ✅ **Context formatting matches production**: Byte-for-byte comparison with `advanced_retriever._format_context()`
2. ✅ **Chunk counts per intent**: Verify 5/10/15 distribution
3. ✅ **Serialization/deserialization**: MultiChunkQAPair to/from dict
4. ✅ **Chunk grouping**: Groups have sufficient chunks for each intent
5. ✅ **Import validation**: All new classes/functions importable
6. ✅ **CLI help messages**: User-friendly documentation

### Recommended

1. **Single-chunk compatibility**: Run same question with 1 chunk, compare with `eval_generation.py`
2. **End-to-end test**: Generate dataset → Run eval → Verify HTML report
3. **Production comparison**: Extract real API context → Replicate in eval → Verify match
4. **Metric correlation**: Check if attribution/coherence correlate with faithfulness

## Performance Considerations

### Dataset Generation

- **Time**: ~10-15 minutes for 30 QA pairs (LLM calls for each)
- **Cost**: Uses Ollama (local, free) by default
- **Parallelization**: Sequential (to avoid overwhelming Ollama)

### Evaluation

- **Time per question**: ~20-30 seconds (generation + 4 judge calls)
  - 1× Generation
  - 2× Core metrics (faithfulness, relevance)
  - 2× Multi-chunk metrics (attribution, coherence)
- **Total for 10 questions**: ~3-5 minutes per model
- **Memory**: Handles up to 15 chunks × 2500 chars = ~37KB per question

### Optimization Opportunities

1. **Parallel judge calls**: Run faithfulness + relevance + attribution + coherence in parallel
2. **Cached judge responses**: Reuse for same question across models
3. **Chunk truncation**: Reduce max_chars_per_chunk for faster processing
4. **Batch dataset generation**: Generate multiple questions per LLM call

## Troubleshooting

### "Multi-chunk dataset not found"

```bash
# Generate dataset first
python -m eval.generate_multichunk_dataset --size 30
```

### "No suitable chunk groups found"

- Need more conversation data (at least 10+ chunks per participant)
- Lower `min_chunks` in grouping logic
- Use smaller chunk counts (e.g., `--chunks 3,5,8`)

### "LLM judge timeout"

- Increase timeout in `compute_chunk_attribution()` / `compute_cross_chunk_coherence()`
- Reduce number of chunks shown to judge (currently 15 max)
- Use faster judge model (`--judge qwen2.5:3b`)

### "Context too long for LLM"

- Reduce `max_chars_per_chunk` in `format_multichunk_context()`
- Limit number of chunks per question
- Use model with larger context window

## Future Enhancements

### Metrics

1. **Source Diversity**: Measure how many unique chunks were used
2. **Temporal Coherence**: For time-based questions, verify chronological accuracy
3. **Participant Attribution**: For multi-participant questions, check correct speaker identification

### Dataset

1. **Question templates**: Predefined templates for consistent generation
2. **Difficulty levels**: Easy/medium/hard based on chunk count + reasoning depth
3. **Human evaluation**: Sample validation of LLM-generated questions

### Reporting

1. **Attribution heatmap**: Visual matrix of chunk usage
2. **Chunk relevance analysis**: Were the right chunks provided?
3. **Error categorization**: Hallucination vs omission vs misattribution

## References

- **Plan document**: Implementation plan with detailed specs
- **eval_generation.py**: Single-chunk evaluation baseline
- **advanced_retriever.py:491-530**: Production context formatting
- **query_analyzer.py:172-191**: Intent → chunk count mapping
- **COMMANDS.md**: Updated with multi-chunk eval commands
