# Phase 0: Complexity Analysis Validation

## Overview

Phase 0 is a **critical validation phase** that determines whether implementing complexity-based model routing is worthwhile. This phase answers:

1. **Quality:** Does the 3B model produce acceptable output compared to 8B?
2. **Performance:** Is the time savings substantial enough (> 20%) to justify implementation?
3. **Resources:** Is RAM management viable with the target machine?
4. **Decision:** Should we proceed with Phase 1+ implementation?

## What Phase 0 Does

### 1. Create Validation Dataset (`create_validation_dataset.py`)

**Input:** Full chunks.json (32,559 chunks)
**Output:** validation_dataset.json (60 representative chunks)

**Process:**
- Computes 7 complexity metrics for each chunk:
  - Participant count (1-5+)
  - Message count (5-50+)
  - Average tokens per message (estimated)
  - Media/links density (%)
  - Lexical diversity (normalized)
  - Dialogue markers (questions, exclamations, emoji)
  - Chunk size

- Classifies chunks into categories:
  - **Simple:** Low complexity (score < 0.35)
  - **Medium:** Moderate complexity (0.35 ≤ score < 0.65)
  - **Complex:** High complexity (score ≥ 0.65)

- Selects 20 representative chunks from each category (~60 total)

**Metrics Explanation:**

| Metric | Formula | Interpretation |
|--------|---------|-----------------|
| **Participants** | count | More participants = more perspectives to track |
| **Tokens/Msg** | total_tokens / message_count | Longer messages = denser content |
| **Media Density** | media_count / message_count | Media requires contextual understanding |
| **Lexical Diversity** | unique_words / sqrt(total_words) | Rich vocabulary = more nuanced meaning |
| **Dialogue Markers** | (? + ! + emoji) / message_count | Emotional intensity = complex sentiment |
| **Chunk Size** | message_count | More messages = more to synthesize |

**Example Complexity Score Calculation:**
```
Simple chunk (score=0.24):
  - 2 participants (0.0 × 0.20)
  - 12 messages (0.0 × 0.15)
  - 18 tokens/msg (0.0 × 0.25)
  - 5% media (0.0 × 0.15)
  - 0.35 lexical diversity (0.0 × 0.15)
  - 0.1 dialogue markers (0.5 × 0.10) = 0.05
  Total: 0.05 < 0.35 → SIMPLE ✅

Complex chunk (score=0.68):
  - 4 participants (0.5 × 0.20) = 0.10
  - 42 messages (1.0 × 0.15) = 0.15
  - 115 tokens/msg (1.0 × 0.25) = 0.25
  - 25% media (0.5 × 0.15) = 0.075
  - 0.85 lexical diversity (1.0 × 0.15) = 0.15
  - 0.6 dialogue markers (1.0 × 0.10) = 0.10
  Total: 0.685 > 0.65 → COMPLEX ✅
```

### 2. Benchmark Models (`benchmark_models.py`)

**Input:** validation_dataset.json (60 chunks)
**Output:** benchmark_report.json (detailed statistics)

**Process:**
For each chunk in the validation dataset:

1. **Enrich with 3B** (ministral-3:3b)
   - Measure: timing, memory delta, output quality
   - Record: summary length, questions generated

2. **Enrich with 8B** (ministral-3:8b)
   - Same measurements as 3B
   - Compare outputs

3. **Analyze Results:**
   - Time delta: How much faster is 3B?
   - Quality ratio: Is 3B output 70%+ of 8B quality?
   - Memory impact: How much RAM per model?

**Requirements:**
- Ollama running (`ollama serve`)
- Both models available:
  ```bash
  ollama pull ministral-3:3b
  ollama pull ministral-3:8b
  ```

**Measurement Points:**

| Metric | 3B Result | 8B Result | Analysis |
|--------|-----------|-----------|----------|
| Enrichment time | ~1.2s (simple) | ~2.1s | 43% faster |
| Summary length | ~150 chars | ~200 chars | Quality ratio? |
| Memory delta | +80MB | +120MB | Peak consumption? |

### 3. Analyze & Decide (`analyze_benchmark.py`)

**Input:** benchmark_report.json
**Output:** GO/NO-GO decision with reasoning

**Decision Criteria:**

1. **Time Gain ≥ 20%?**
   - Projection: baseline (8B only) vs. with routing
   - Example: 8.2 hours → 6.5 hours = 21% gain ✅

2. **Quality Acceptable (3B ≥ 70% of 8B)?**
   - Focus: simple chunk quality
   - Metric: average summary length, question count
   - Example: 3B avg=145 chars, 8B avg=200 chars = 72.5% ✅

3. **Resource Overhead?**
   - Dual-load: +2-3GB RAM for second model
   - On-demand: ~15s overhead per model switch
   - Batch: Feasible but more complex implementation

**Output Example:**
```
✅ GO DECISION

Time Gain: 26% (8.2h → 6.1h = 2.1 hours saved)
Quality: 3B 72.5% of 8B on simple chunks
Strategy: dual-load (pre-load both models)

Projection (32,559 chunks):
  Simple (40%): 3B @ 1.2s = 39,072s
  Medium (30%): 3B @ 1.8s = 17,505s
  Complex (30%): 8B @ 2.8s = 27,348s
  Total: 83,925s = 23.3 hours vs baseline 30.8 hours
```

## Running Phase 0

### Prerequisites

```bash
# Install dependencies
pip install psutil requests

# Start Ollama
ollama serve

# In another terminal, pull models
ollama pull ministral-3:3b
ollama pull ministral-3:8b
```

### Step 1: Create Validation Dataset

```bash
cd /Users/ismaelsebbane/dev/lab/instagram-assistant

python scripts/create_validation_dataset.py \
  --input rag_data/chunks.json \
  --output validation_dataset.json \
  --per-category 20
```

Expected output:
```
✅ Loaded 32,559 chunks
✅ Dataset Creation Summary
Total chunks selected: 60
  - Simple:  20 chunks
  - Medium:  20 chunks
  - Complex: 20 chunks
```

Check the dataset:
```bash
python -c "
import json
with open('validation_dataset.json') as f:
    chunks = json.load(f)
print(f'Loaded {len(chunks)} chunks')
print(f'Simple: {len([c for c in chunks if c[\"classification\"][\"category\"] == \"simple\"])}')
print(f'Medium: {len([c for c in chunks if c[\"classification\"][\"category\"] == \"medium\"])}')
print(f'Complex: {len([c for c in chunks if c[\"classification\"][\"category\"] == \"complex\"])}')
"
```

### Step 2: Run Benchmark (⏱️ Takes 30-60 minutes)

```bash
python scripts/benchmark_models.py \
  --dataset validation_dataset.json \
  --output benchmark_report.json \
  --strategy dual
```

For quick testing (3 chunks per category):
```bash
python scripts/benchmark_models.py \
  --dataset validation_dataset.json \
  --output benchmark_report_test.json \
  --limit 9  # 3 simple + 3 medium + 3 complex
```

Expected output:
```
📂 Loading validation dataset...
✅ Loaded 60 chunks for benchmarking
🔥 Warming up models...
🏃 Running benchmarks on 60 chunks...
[1/60] 📊 Benchmarking conv_001_chunk_000 (simple)... 3B: 1245ms 8B: 2156ms
[2/60] 📊 Benchmarking conv_005_chunk_003 (simple)... 3B: 1189ms 8B: 2089ms
...
✅ Completed 60 benchmarks
💾 Report saved to benchmark_report.json
```

### Step 3: Analyze Results

```bash
python scripts/analyze_benchmark.py benchmark_report.json
```

Expected output:
```
════════════════════════════════════════════════════════════════
                  BENCHMARK RESULTS SUMMARY
════════════════════════════════════════════════════════════════

Status: success
Validation Chunks Processed: 60

ENRICHMENT TIME BY CATEGORY:
Category    3B (ms)      8B (ms)      Gain %
simple      1245         2156         42.2
medium      1812         2734         33.7
complex     2401         2984         19.5

PROJECTED RESULTS (32,559 chunks):
  Baseline (8B only):        8.2 hours
  With intelligent routing:  6.1 hours
  Gain:                      26.0% (2.1 hours)

DECISION: ✅ GO
Strategy: dual-load
```

## Expected Outcomes

### If GO Decision

**Green flags:**
- ✅ Time savings ≥ 20%
- ✅ 3B quality ≥ 70% on simple chunks
- ✅ Overall quality degradation minimal
- ✅ RAM overhead acceptable

**Next phase:**
- Implement Phase 1: ComplexityAnalyzer
- Integrate into ChunkEnricher
- Test on 500-1000 chunks
- Full indexing with new system

### If NO-GO Decision

**Red flags:**
- ❌ Time savings < 20% (not worth complexity)
- ❌ 3B quality < 70% (too much degradation)
- ❌ RAM overhead too high
- ❌ Model switching overhead dominates gains

**Alternatives to explore:**
1. Use quantized 8B (Q4) instead of dual models
2. Optimize prompts to reduce generation time
3. Batch process chunks with caching
4. Try different models (Qwen, Llama, etc.)

## Key Metrics Reference

### Chunk Complexity Score (0.0-1.0)

```python
score = (
    participants_factor * 0.20 +
    density_factor * 0.25 +
    media_factor * 0.15 +
    size_factor * 0.15 +
    lexical_factor * 0.15 +
    dialogue_factor * 0.10
)
```

**Factor Mapping:**

| Metric | Low (0.0) | Medium (0.5) | High (1.0) |
|--------|-----------|--------------|-----------|
| **Participants** | 1-2 | 3-4 | 5+ |
| **Tokens/Msg** | <50 | 50-100 | >100 |
| **Media Density** | <10% | 10-30% | >30% |
| **Chunk Size** | <15 msg | 15-35 msg | >35 msg |
| **Lexical Div** | <0.5 | 0.5-0.8 | >0.8 |
| **Dialogue Mark** | <0.2/msg | 0.2-0.5/msg | >0.5/msg |

### Classification Thresholds

| Category | Score Range | Recommended Model |
|----------|-------------|-------------------|
| Simple | < 0.35 | 3B (fast) |
| Medium | 0.35-0.65 | 3B (configurable) |
| Complex | ≥ 0.65 | 8B (quality) |

## Troubleshooting

### Ollama Connection Error

```
❌ Cannot connect to Ollama: [Errno 111] Connection refused
```

**Solution:**
```bash
# Start Ollama in one terminal
ollama serve

# Or restart the service
pkill ollama
ollama serve
```

### Models Not Available

```
❌ Error enriching chunk: pull manifest unknown
```

**Solution:**
```bash
ollama pull ministral-3:3b
ollama pull ministral-3:8b
ollama list  # Verify both are listed
```

### Out of Memory

```
❌ Error: OOM killer / CUDA out of memory
```

**Solutions:**
1. Reduce batch size: `--limit 10`
2. Use `on-demand` strategy instead of `dual`
3. Add swap space: `sudo fallocate -l 8G /swapfile`
4. Run on machine with more RAM

### Benchmark Stuck

```
[10/60] 📊 Benchmarking... (hanging)
```

**Diagnosis:**
- Check Ollama status: `curl http://localhost:11434/api/tags`
- Check GPU: `nvidia-smi` or `gpu-stat`
- Check disk space: `df -h`

**Solution:**
- Restart Ollama: `pkill ollama && ollama serve`
- Reduce batch: Re-run with `--limit 5`

## Files Generated

| File | Size | Purpose |
|------|------|---------|
| `validation_dataset.json` | ~2MB | 60 representative chunks with metrics |
| `benchmark_report.json` | ~100KB | Detailed timing and quality comparison |
| Various logs | N/A | Diagnostic output during runs |

## Key Learnings

After Phase 0, you'll have concrete data on:

1. **Model Speed Trade-off**
   - How much faster is 3B vs 8B per chunk type?
   - Is the speed difference consistent?

2. **Quality Trade-off**
   - What aspects of enrichment degrade with 3B?
   - Can we adjust thresholds to protect quality?

3. **Practical Distribution**
   - What % of your chunks are simple/medium/complex?
   - Is the distribution skewed toward simple or complex?

4. **Resource Constraints**
   - Can you dual-load both models?
   - What's the feasible loading strategy?

5. **ROI Calculation**
   - How many hours saved for full dataset?
   - Is it worth the implementation complexity?

## Next Steps (If GO)

Phase 1 implementation files:

1. **Create `rag_pipeline/complexity_analyzer.py`**
   - `ChunkComplexityAnalyzer` class
   - Metric computation methods
   - Classification logic

2. **Modify `rag_pipeline/enricher.py`**
   - Add `_preload_models()` method
   - Add `_ensure_model_loaded()` method
   - Add routing logic to `enrich_chunk()`

3. **Extend `rag_pipeline/config.py`**
   - Add complexity routing parameters
   - Add model loading strategy options
   - Add seuil configurables

4. **Create `rag_pipeline/enrichment_log.py`**
   - `EnrichmentLogger` class
   - CSV export functionality
   - Statistics collection

5. **Update `setup_rag.py`**
   - Add `--model-strategy` parameter
   - Display routing statistics after indexation
   - Support partial indexing for testing

## References

- Plan document: `/PLAN.md` (full specifications)
- Enricher implementation: `rag_pipeline/enricher.py` lines 63-248
- Chunk structure: `rag_pipeline/chunker.py` lines 20-80
- Eval tools: `eval/enrichment/eval_enrichment.py`
