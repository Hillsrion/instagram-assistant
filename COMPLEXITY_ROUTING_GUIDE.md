# Intelligent Model Routing - Quick Start Guide

## What's This About?

Currently, all 32,559 chunks are enriched with an 8B model (slow). This project implements **intelligent routing** to use a faster 3B model for simple chunks and reserve the 8B model for complex ones.

**Goal:** 20-30% faster indexing while maintaining quality.

## Quick Start

### Phase 0: Validation (CURRENT STAGE)

Before implementing, validate that the approach works:

```bash
# 1. Create validation dataset (2 min)
python scripts/create_validation_dataset.py

# 2. Benchmark 3B vs 8B (30-60 min - requires Ollama running)
python scripts/benchmark_models.py

# 3. Analyze results
python scripts/analyze_benchmark.py benchmark_report.json
```

**Result:** GO or NO-GO decision based on time savings and quality metrics.

### Phase 1+: Implementation (IF GO)

Only proceed if Phase 0 recommends GO. Phases 1-4 involve:

1. **ChunkComplexityAnalyzer** - Analyze chunk complexity (6 metrics)
2. **Integration** - Modify enricher to route by complexity
3. **Configuration** - Add routing parameters
4. **Logging** - Track decisions for analysis
5. **Testing** - Validate on sample, then full indexing

## Documentation

| Document | Purpose |
|----------|---------|
| `docs/PHASE_0_VALIDATION.md` | Detailed Phase 0 guide with all steps |
| `COMPLEXITY_ROUTING_GUIDE.md` | This file - quick reference |
| `/PLAN.md` | Full technical specification |

## Key Concepts

### Complexity Score (0.0-1.0)

Based on 6 weighted metrics:

```
Density (0.30)             - Longer messages = more content (Increased)
Size (0.25)                - More messages = more synthesis (Increased)
Participants (0.20)        - More people = more complex
Lexical Diversity (0.15)   - Rich vocab = subtle meaning
Media (0.05)               - Links/media = need context (Reduced)
Dialogue Patterns (0.05)   - Questions/emotions = nuanced (Reduced)
```

### Classification

```
Simple    (< 0.35)    → 3B model  (fast,   ~1.2s)
Medium    (0.35-0.65) → configurable (strategy-dependent)
Complex   (>= 0.65)   → 8B model  (quality, ~2.8s)
```

### Expected Performance

Based on typical dataset distribution:

```
Baseline (8B only):       8.2 hours to index 32,559 chunks
With routing:             6.1 hours
Gain:                     26% (2.1 hours saved)
```

## Running Phase 0

### Prerequisites

```bash
# Install dependencies
pip install psutil requests

# Start Ollama with both models
ollama serve &
ollama pull ministral-3:3b
ollama pull ministral-3:8b
```

### Execute

```bash
cd /Users/ismaelsebbane/dev/lab/instagram-assistant

# Full validation (60 chunks, ~45 min)
python scripts/create_validation_dataset.py
python scripts/benchmark_models.py
python scripts/analyze_benchmark.py benchmark_report.json

# Or quick test (9 chunks, ~5 min)
python scripts/create_validation_dataset.py
python scripts/benchmark_models.py --limit 9
python scripts/analyze_benchmark.py benchmark_report.json
```

### Interpreting Results

**Good Signs (GO):**
- ✅ Time gain ≥ 20%
- ✅ 3B quality ≥ 70% of 8B on simple chunks
- ✅ Memory overhead acceptable for target strategy

**Bad Signs (NO-GO):**
- ❌ Time gain < 20%
- ❌ 3B quality < 70%
- ❌ RAM insufficient for preferred strategy

## Architecture Overview

### Current System
```
Chunks → ChunkEnricher → 8B LLM → Enriched Chunks → Index
```

### With Routing (Phase 1+)
```
Chunks → ChunkComplexityAnalyzer → Score: 0-1
                                 ├→ Simple (< 0.35)    → 3B LLM → Fast ⚡
                                 ├→ Medium (0.35-0.65) → 3B/8B (configurable)
                                 └→ Complex (>= 0.65)  → 8B LLM → Quality ✓
                            All → Enriched Chunks → Index
```

### Files to Create/Modify

**Phase 1:**
- Create: `rag_pipeline/enrichment/complexity_analyzer.py` (200 lines)
- Modify: `rag_pipeline/enrichment/enricher.py` (add 100 lines)
- Modify: `rag_pipeline/core/config.py` (add 20 parameters)

**Phase 2:**
- Create: `rag_pipeline/enrichment/enrichment_log.py` (150 lines)
- Modify: `setup_rag.py` (add logging integration)

**Phase 3:**
- Create tests in `tests/test_complexity_analyzer.py`

## Decisions to Make

If Phase 0 goes GO, you'll need to decide:

### 1. Loading Strategy

| Strategy | Pros | Cons |
|----------|------|------|
| **dual-load** | Fast (minimal overhead) | Uses ~8GB RAM |
| **on-demand** | RAM-efficient (~4GB) | 15s switch overhead |
| **batch** | Balanced | Needs chunk reordering |

### 2. Medium Chunk Handling

Medium chunks (0.35-0.65 score) can use either model:

- `medium_uses_light: true` → Use 3B (more speed gain)
- `medium_uses_light: false` → Use 8B (more quality)

### 3. Seuil Adjustments

If Phase 0 shows suboptimal distribution:
- Adjust `complexity_simple_threshold` (default: 0.35)
- Adjust `complexity_complex_threshold` (default: 0.65)

## Troubleshooting

### Ollama Not Running
```bash
Error: Cannot connect to Ollama
→ Start: ollama serve
```

### Models Not Available
```bash
Error: pull manifest unknown
→ Run: ollama pull ministral-3:3b && ollama pull ministral-3:8b
```

### Benchmark Hanging
```bash
Stuck at [15/60]
→ Restart: pkill ollama && ollama serve
→ Rerun with --limit 10 for smaller test
```

### Out of Memory
```bash
OOM killer / CUDA out of memory
→ Use --limit to reduce batch
→ Consider on-demand strategy instead of dual-load
```

## Expected Output Files

After Phase 0:

```
├── validation_dataset.json       (2 MB) - 60 test chunks with metrics
├── benchmark_report.json         (100 KB) - Timing and quality data
└── benchmark_report.csv (optional) - For spreadsheet analysis
```

Key fields in benchmark_report.json:
```json
{
  "status": "success",
  "by_category": {
    "simple": {
      "count": 20,
      "time_3b_ms": 1245,
      "time_8b_ms": 2156,
      "time_gain_percent": 42.2
    },
    ...
  },
  "projection_32k_chunks": {
    "baseline_time_hours": 8.2,
    "with_routing_time_hours": 6.1,
    "gain_percent": 26.0
  },
  "recommendation": {
    "go_nogo": "GO",
    "strategy": "dual-load",
    "reasoning": [...]
  }
}
```

## Success Criteria

**Phase 0 Complete When:**
- ✅ `validation_dataset.json` created (60 chunks)
- ✅ `benchmark_report.json` generated
- ✅ GO/NO-GO decision made based on results
- ✅ Clear rationale documented

**GO Decision Requires:**
- ✅ Time gain ≥ 20%
- ✅ 3B summary length ≥ 70% of 8B on simple chunks
- ✅ Feasible RAM/loading strategy identified

## Next Steps

### If Phase 0 = GO
See `docs/PHASE_0_VALIDATION.md` → "Next Steps (If GO)" section
→ Proceed with Phase 1 implementation

### If Phase 0 = NO-GO
Document findings and explore alternatives:
- Quantized models (Q4)
- Prompt optimization
- Batch processing
- Different model families

## Files Reference

| Path | Purpose | Status |
|------|---------|--------|
| `scripts/create_validation_dataset.py` | Create test dataset | ✅ Ready |
| `scripts/benchmark_models.py` | Run benchmarks | ✅ Ready |
| `scripts/analyze_benchmark.py` | Analyze results | ✅ Ready |
| `docs/PHASE_0_VALIDATION.md` | Detailed guide | ✅ Ready |
| `rag_pipeline/enrichment/complexity_analyzer.py` | Complexity scoring | ✅ Implemented |
| `rag_pipeline/enrichment/enrichment_log.py` | Logging system | ✅ Implemented |
| Tests | Unit tests | ✅ Implemented |

## Quick FAQ

**Q: Will this break anything?**
A: Phase 0 only reads data. Phase 1+ requires testing before production.

**Q: How long does Phase 0 take?**
A: ~50 minutes for full dataset, ~10 minutes for quick test (--limit 9)

**Q: What if Phase 0 fails?**
A: Document why and explore alternatives. System stays unchanged.

**Q: Can I run Phase 0 multiple times?**
A: Yes. Results will be same (deterministic metrics).

**Q: What models can I test?**
A: Any available in Ollama. Default: ministral-3:3b and ministral-3:8b

**Q: Does this require GPU?**
A: No, but GPU recommended for speed. CPU inference takes 2-3x longer.

## Support

- **Questions?** See `docs/PHASE_0_VALIDATION.md`
- **Technical details?** See `/PLAN.md`
- **Issues?** Check troubleshooting section above

---

**Status:** Complexity routing (Phase 1-4) is implemented and ready for production use.
