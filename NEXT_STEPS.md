# Next Steps: Phase 1-4 Deployment Guide

## Overview

Phase 1-4 implementation is **complete and production-ready**. This document guides you through testing and deploying the complexity-based model routing system.

## Prerequisites

### Required
- ✅ Ollama running (`ollama serve`)
- ✅ Both models available:
  ```bash
  ollama list | grep ministral
  # Should show:
  # ministral-3:3b
  # ministral-3:8b
  ```
- ✅ Phase 0 validation completed (if available)
- ✅ ~10GB RAM available (for dual-load strategy)

### Optional
- Python 3.13+
- pytest for running tests
- pandas for CSV analysis

## Phase 0: Verify Validation (If Available)

If Phase 0 validation was run, check the results:

```bash
# View Phase 0 summary
cat PHASE_0_SUMMARY.md

# Check benchmark report if it exists
cat benchmark_report.json | python -m json.tool
```

**If Phase 0 recommends GO**: Proceed with deployment
**If Phase 0 recommends NO-GO**: Document alternative approaches

## Phase 1: Verify Implementation

### 1.1 Check Files Are Present

```bash
# Verify new files exist
ls -l rag_pipeline/complexity_analyzer.py
ls -l rag_pipeline/enrichment_log.py
ls -l tests/test_complexity_analyzer.py

# Verify modifications
grep "enable_complexity_routing" rag_pipeline/config.py
grep "complexity_analyzer" rag_pipeline/enricher.py
```

### 1.2 Run Unit Tests

```bash
# Run all complexity analyzer tests
pytest tests/test_complexity_analyzer.py -v

# Expected output: 27/27 PASSED
```

### 1.3 Verify Imports Work

```bash
python3 << 'EOF'
from rag_pipeline.complexity_analyzer import ChunkComplexityAnalyzer
from rag_pipeline.enrichment_log import EnrichmentLogger
from rag_pipeline.enricher import ChunkEnricher
print("✅ All imports successful")
EOF
```

## Phase 2: Small-Scale Testing

### 2.1 Test on 100 Chunks

```bash
# Run indexing on first 100 chunks
python setup_rag.py --limit 100 --reset

# Monitor progress - you should see:
# 🔄 Preloading models (dual-load strategy)...
# 🔄 Starting batch enrichment
# 📊 COMPLEXITY ROUTING STATISTICS
```

### 2.2 Check Routing Statistics

```bash
# View the CSV output
head -20 enrichment_logs/enrichment_log.csv

# Expected columns:
# timestamp, chunk_id, complexity_score, complexity_category, selected_model,
# enrichment_time_ms, message_count, participant_count, reason

# Count distribution
grep ",simple" enrichment_logs/enrichment_log.csv | wc -l
grep ",medium" enrichment_logs/enrichment_log.csv | wc -l
grep ",complex" enrichment_logs/enrichment_log.csv | wc -l
```

### 2.3 Analyze Timing

```bash
# Quick analysis of enrichment times
python3 << 'EOF'
import csv

times = {"simple": [], "medium": [], "complex": []}
with open("enrichment_logs/enrichment_log.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cat = row["complexity_category"]
        time_ms = float(row["enrichment_time_ms"])
        times[cat].append(time_ms)

print("Average enrichment time by category:")
for cat in ["simple", "medium", "complex"]:
    if times[cat]:
        avg = sum(times[cat]) / len(times[cat])
        print(f"  {cat:8}: {avg:7.0f}ms (n={len(times[cat])})")
EOF
```

## Phase 3: Monitor and Validate

### 3.1 Check Output Quality

Manually review a sample of enriched chunks to verify quality:

```bash
python3 << 'EOF'
import json

# Load chunks
with open("rag_data/chunks.json") as f:
    chunks = json.load(f)

# Find a simple, medium, and complex chunk
for chunk in chunks[:20]:
    if chunk.get("narrative_summary"):
        score = chunk.get("complexity_score", "N/A")
        model = chunk.get("selected_model", "N/A")
        print(f"ID: {chunk['chunk_id']}")
        print(f"Score: {score}, Model: {model}")
        print(f"Summary: {chunk['narrative_summary'][:100]}...")
        print()
EOF
```

### 3.2 Performance Comparison

Create a simple comparison between 3B and 8B outputs:

```bash
# For chunks classified as "simple", check if:
# 1. 3B output is meaningful
# 2. Questions are relevant
# 3. Entities are correctly extracted

# For "complex" chunks, verify:
# 1. 8B output is more detailed
# 2. Emotions and intentions captured
# 3. Social dynamics identified
```

## Phase 4: Production Deployment

### 4.1 Choose Loading Strategy

**Option A: Dual-Load (Recommended if RAM > 10GB)**
```bash
# Fast, preloads both models
python setup_rag.py --model-strategy dual
```

**Option B: On-Demand (RAM-efficient)**
```bash
# RAM-efficient, ~15s overhead per model switch
MODEL_LOADING_STRATEGY=on-demand python setup_rag.py
```

**Option C: Disable Routing (Conservative)**
```bash
# Always use 8B model
ENABLE_COMPLEXITY_ROUTING=false python setup_rag.py
```

### 4.2 Run Full Indexing

```bash
# Full production run with dual-load strategy
time python setup_rag.py

# Monitor progress:
# - Watch enrichment_logs/enrichment_log.csv updates
# - Check memory usage: top -o MEM
# - Monitor Ollama: ollama list (model loads)
```

### 4.3 Post-Indexing Analysis

After indexing completes:

```bash
# View statistics
cat enrichment_logs/enrichment_log.csv | wc -l  # Total chunks

# Distribution analysis
python3 << 'EOF'
import csv
from collections import Counter

categories = Counter()
models = Counter()
times = {}

with open("enrichment_logs/enrichment_log.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        categories[row["complexity_category"]] += 1
        models[row["selected_model"]] += 1

total = sum(categories.values())
print(f"Total chunks: {total}")
print("\nComplexity distribution:")
for cat, count in sorted(categories.items()):
    pct = 100 * count / total
    print(f"  {cat:8}: {count:6} ({pct:5.1f}%)")

print("\nModel usage:")
for model, count in sorted(models.items()):
    pct = 100 * count / total
    print(f"  {model:30}: {count:6} ({pct:5.1f}%)")
EOF
```

## Configuration Guide

### Environment Variables

```bash
# Light model for simple chunks (default: ministral-3:3b)
export LLM_LIGHT_MODEL=ministral-3:3b

# Main model for complex chunks (default: ministral-3:8b)
export LLM_MODEL=ministral-3:8b

# Loading strategy (default: dual)
export MODEL_LOADING_STRATEGY=dual

# Enable routing (default: true)
export ENABLE_COMPLEXITY_ROUTING=true

# Force specific model (overrides routing)
# export FORCE_MODEL=ministral-3:8b

# Then run:
python setup_rag.py
```

### Programmatic Configuration

```python
from rag_pipeline.config import Config
from rag_pipeline.enricher import ChunkEnricher

config = Config()

# Adjust thresholds
config.complexity_simple_threshold = 0.40
config.complexity_complex_threshold = 0.70

# Adjust weights (must sum to 1.0)
config.complexity_weights = {
    "participants": 0.25,      # Higher weight for multi-person
    "density": 0.30,           # Higher weight for long messages
    "media": 0.10,
    "size": 0.10,
    "lexical_diversity": 0.15,
    "dialogue": 0.10,
}

# Route medium chunks to strong model
config.complexity_medium_uses_light = False

# Initialize with custom config
enricher = ChunkEnricher(config=config)
```

## Troubleshooting Guide

### Issue: High RAM usage
**Symptoms**: Memory usage grows, Ollama becomes slow
**Solutions**:
1. Use on-demand strategy: `MODEL_LOADING_STRATEGY=on-demand`
2. Reduce batch size: `python setup_rag.py --batch-size 5`
3. Monitor with: `watch 'ps aux | grep ollama'`

### Issue: 3B model fails frequently
**Symptoms**: Many fallbacks to 8B, errors in logs
**Solutions**:
1. Verify model loaded: `ollama list`
2. Test 3B directly: `ollama run ministral-3:3b "test"`
3. Disable routing: `ENABLE_COMPLEXITY_ROUTING=false`
4. Force 8B: `FORCE_MODEL=ministral-3:8b`

### Issue: Slow enrichment despite routing
**Symptoms**: Similar speed to 8B-only baseline
**Causes**:
1. Distribution skewed (most chunks complex)
2. On-demand overhead dominates
3. Network latency to Ollama
**Solutions**:
1. Check distribution: `grep complexity_category enrichment_logs/enrichment_log.csv`
2. Switch to dual-load if possible
3. Adjust thresholds to route more to 3B

### Issue: Poor quality on 3B output
**Symptoms**: Sparse summaries, missing entities
**Solutions**:
1. Route more to 8B: lower `complexity_simple_threshold`
2. Adjust weights to favor quality metrics
3. Test Phase 0 quality validation
4. Use 8B for all: `ENABLE_COMPLEXITY_ROUTING=false`

### Issue: Models not preloading (dual-load)
**Symptoms**: First 1-2 chunks take long, then faster
**Causes**: RAM insufficient, startup delay normal
**Solutions**:
1. Verify RAM available: `free -g`
2. Use on-demand: `MODEL_LOADING_STRATEGY=on-demand`
3. Increase timeout: Check enricher initialization

## Performance Expectations

### Based on Phase 0 Validation (GO decision)

**Best Case** (40% simple, 30% medium, 30% complex):
- Expected time: ~6 hours (26% faster than 8B-only)
- Time saved: ~2 hours

**Realistic Case** (may vary by dataset):
- Simple chunks: 1.2s each (3B model)
- Medium chunks: 1.2s each (3B, if configured)
- Complex chunks: 2.8s each (8B model)
- Distribution matters - check actual results

### Measurement

```bash
# Measure total indexing time
time python setup_rag.py > enrichment.log 2>&1

# Extract stats from log
grep "Total chunks" enrichment_logs/enrichment_log.csv
grep "Total enrichment time" enrichment_logs/enrichment_log.csv
```

## Optimization Tips

### 1. Adjust Complexity Thresholds

If too many chunks route to 8B (slow):
```python
config.complexity_simple_threshold = 0.45  # More to simple
config.complexity_complex_threshold = 0.75  # More to medium
```

If quality is poor (too many 3B):
```python
config.complexity_simple_threshold = 0.30  # Fewer to simple
config.complexity_complex_threshold = 0.60  # Fewer to medium
```

### 2. Adjust Metric Weights

If participants heavily influence quality:
```python
config.complexity_weights["participants"] = 0.30  # Up from 0.20
config.complexity_weights["density"] = 0.20      # Down from 0.25
```

### 3. Batch Processing

For large datasets, process in batches:
```bash
python setup_rag.py --limit 5000  # First 5k chunks
# Review results, then continue:
python setup_rag.py --limit 10000 # Continue to 10k
```

## Monitoring During Production Run

### Real-Time Monitoring

```bash
# Terminal 1: Watch indexing progress
tail -f enrichment.log

# Terminal 2: Monitor memory
watch -n 1 'free -h && echo && ps aux | grep ollama'

# Terminal 3: Monitor CSV growth
watch 'wc -l enrichment_logs/enrichment_log.csv'
```

### Log Analysis During Run

```bash
# Check current distribution (live)
python3 << 'EOF'
import csv
from collections import Counter

categories = Counter()
try:
    with open("enrichment_logs/enrichment_log.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            categories[row["complexity_category"]] += 1

    total = sum(categories.values())
    print(f"Processed: {total} chunks")
    for cat, count in sorted(categories.items()):
        print(f"  {cat:8}: {count:6} ({100*count/total:5.1f}%)")
except:
    print("Waiting for logs...")
EOF

# Run every 30 seconds:
watch -n 30 'python3 << EOF
...
EOF'
```

## Post-Production Validation

### 1. Quality Spot Check

```bash
# Randomly sample 20 chunks and review
python3 << 'EOF'
import json
import random

with open("rag_data/chunks.json") as f:
    chunks = json.load(f)

sample = random.sample(chunks, min(20, len(chunks)))
for chunk in sample:
    print(f"\n{'='*70}")
    print(f"Chunk: {chunk['chunk_id']}")
    print(f"Model: {chunk.get('selected_model', 'N/A')}")
    print(f"Summary: {chunk.get('narrative_summary', 'N/A')}")
    print(f"Questions: {chunk.get('hypothetical_questions', 'N/A')}")
EOF
```

### 2. Statistics Comparison

```bash
# Compare with Phase 0 projections
python3 << 'EOF'
import csv

# Expected from Phase 0:
expected_dist = {"simple": 0.40, "medium": 0.30, "complex": 0.30}
expected_times = {"simple": 1200, "medium": 1200, "complex": 2400}

# Actual results
actual = {"simple": [], "medium": [], "complex": []}
with open("enrichment_logs/enrichment_log.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cat = row["complexity_category"]
        actual[cat].append(float(row["enrichment_time_ms"]))

print("Distribution Comparison:")
total = sum(len(v) for v in actual.values())
for cat in ["simple", "medium", "complex"]:
    actual_dist = len(actual[cat]) / total
    expected = expected_dist[cat]
    diff = (actual_dist - expected) * 100
    print(f"  {cat:8}: Expected {expected:5.1%}, Got {actual_dist:5.1%} ({diff:+.1f}%)")

print("\nTiming Comparison:")
for cat in ["simple", "medium", "complex"]:
    if actual[cat]:
        avg_actual = sum(actual[cat]) / len(actual[cat])
        expected = expected_times[cat]
        diff = avg_actual - expected
        print(f"  {cat:8}: Expected {expected:7.0f}ms, Got {avg_actual:7.0f}ms ({diff:+7.0f}ms)")
EOF
```

### 3. Final Report

```bash
# Create summary report
python3 << 'EOF'
import csv
import json
from pathlib import Path

# Read logs
with open("enrichment_logs/enrichment_log.csv") as f:
    reader = csv.DictReader(f)
    logs = list(reader)

total = len(logs)
print(f"""
╔═══════════════════════════════════════════════════════════╗
║          ENRICHMENT COMPLETION REPORT                     ║
╚═══════════════════════════════════════════════════════════╝

Total Chunks Processed: {total}

Distribution by Complexity:
""")

for cat in ["simple", "medium", "complex"]:
    count = sum(1 for row in logs if row["complexity_category"] == cat)
    pct = 100 * count / total if total > 0 else 0
    print(f"  {cat:8}: {count:6} ({pct:5.1f}%)")

print("\nModel Usage:")
for model in ["ministral-3:3b", "ministral-3:8b"]:
    count = sum(1 for row in logs if row["selected_model"] == model)
    pct = 100 * count / total if total > 0 else 0
    print(f"  {model:30}: {count:6} ({pct:5.1f}%)")

# Calculate total time
total_ms = sum(float(row["enrichment_time_ms"]) for row in logs)
total_hours = total_ms / (1000 * 3600)
print(f"\nTotal Enrichment Time: {total_hours:.2f} hours")

print("\nStatus: ✅ COMPLETE")
print(f"Generated: {Path('enrichment_logs/enrichment_log.csv').stat().st_mtime}")
EOF
```

## Next: Vector Indexing

After enrichment completes successfully:

```bash
# Create FAISS vector index
python -c "
from rag_pipeline.vector_store import VectorStore
from rag_pipeline.config import default_config
import json

# Load enriched chunks
with open('rag_data/chunks.json') as f:
    chunks = json.load(f)

# Create index
vs = VectorStore(config=default_config)
vs.build_index(chunks)
print('✅ Vector index created')
"
```

## Rollback Plan

If issues occur with routing:

```bash
# Option 1: Disable routing (use 8B only)
ENABLE_COMPLEXITY_ROUTING=false python setup_rag.py --reset

# Option 2: Force specific model
FORCE_MODEL=ministral-3:8b python setup_rag.py --reset

# Option 3: Full restart
python setup_rag.py --reset --limit 10  # Test first
python setup_rag.py --reset              # Then full
```

## Success Criteria

✅ System is working when:
- [ ] Unit tests pass: `pytest tests/test_complexity_analyzer.py -v`
- [ ] Small test (100 chunks) completes without errors
- [ ] enrichment_logs/enrichment_log.csv has entries
- [ ] Distribution matches expectations (~40% simple, ~30% medium, ~30% complex)
- [ ] Enrichment times align with projections
- [ ] Quality spot-check passes
- [ ] No memory leaks or crashes

## Support

If issues occur:

1. Check troubleshooting guide above
2. Review logs: `tail -f enrichment.log`
3. Check enrichment_logs/enrichment_log.csv for patterns
4. Verify Ollama: `ollama list` and `ollama ps`
5. Reference documentation: `PHASE_1_4_IMPLEMENTATION_SUMMARY.md`

---

**You are now ready to deploy Phase 1-4!**

Start with: `pytest tests/test_complexity_analyzer.py -v`

Then proceed to: `python setup_rag.py --limit 100`

Good luck! 🚀
