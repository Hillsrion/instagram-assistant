# GPU/CPU Local Sharding for Enrichment

## Overview

GPU/CPU local sharding distributes enrichment processing between two Ollama instances running on the same machine, using different compute resources (GPU vs CPU).

**Key differences:**
- **Local sharding:** Both instances on one machine, different compute resources (this guide)
- **Distributed enrichment:** Multiple machines, same instance type per machine (see [AGENTS.md](../AGENTS.md))

**Why?** Enrichment is the bottleneck (~90 hours for 32k chunks). Routing small chunks to CPU and large chunks to GPU optimizes processing speed without sacrificing quality.

---

## Prerequisites

- Single machine with GPU support (NVIDIA, AMD, or Apple Metal)
- Ollama installed and working
- Sufficient RAM for dual instances (~2-4GB per instance)
- Two available ports (default: 11434 for GPU, 11435 for CPU)

---

## Setup Instructions

### 1. Pull Models on Both Instances

Prepare your two Ollama ports with the same model:

```bash
# GPU instance (default port 11434)
ollama pull ministral-3:8b

# CPU instance (port 11435)
OLLAMA_HOST=0.0.0.0:11435 ollama pull ministral-3:8b
```

Both instances must have the **same model** to ensure consistent output quality.

### 2. Configure `.env`

Edit `.env` to enable sharding and configure GPU/CPU URLs:

```bash
# Enable local GPU/CPU sharding (required)
USE_LOCAL_SHARDING=true

# GPU instance (GPU acceleration enabled)
OLLAMA_URL_GPU=http://localhost:11434

# CPU instance (no GPU acceleration)
OLLAMA_URL_CPU=http://localhost:11435

# Route chunks with >=20 messages to GPU, <20 to CPU
ENRICHMENT_CHUNK_THRESHOLD=20
```

**Important:** Sharding is disabled by default. You must explicitly set `USE_LOCAL_SHARDING=true` to enable it, even if GPU/CPU URLs are configured. This prevents accidental activation.

**Threshold tuning:**
- **Higher (e.g., 30):** More chunks to CPU (faster overall, slightly lower quality)
- **Lower (e.g., 10):** More chunks to GPU (higher quality, slower overall)
- **Default (20):** Balanced tradeoff

### 3. Start Both Ollama Instances

**Terminal 1 (GPU instance):**
```bash
ollama serve
```
Runs on `http://localhost:11434` (default)

**Terminal 2 (CPU instance):**
```bash
OLLAMA_HOST=0.0.0.0:11435 OLLAMA_NUM_GPU=0 ollama serve
```

- `OLLAMA_HOST=0.0.0.0:11435`: Bind to port 11435
- `OLLAMA_NUM_GPU=0`: Disable GPU acceleration on this instance

### 4. Start Enrichment

**Terminal 3:**
```bash
python setup_enrich.py
```

**Alternative: Enable sharding via command-line flag (overrides config):**
```bash
# Enable sharding (even if USE_LOCAL_SHARDING=false in .env)
python setup_enrich.py --enable-local-sharding

# Disable sharding (even if USE_LOCAL_SHARDING=true in .env)
python setup_enrich.py --disable-local-sharding
```

**Expected output:**
```
[Enricher] GPU/CPU Sharding ENABLED
  GPU: http://localhost:11434
  CPU: http://localhost:11435
  Threshold: 20 messages
✓ GPU Ollama instance healthy at http://localhost:11434
✓ CPU Ollama instance healthy at http://localhost:11435
```

Enrichment will automatically route chunks based on message count.

---

## Failover Behavior

### CPU Down (Fallback)
If the CPU instance becomes unavailable:
```
⚠️  CPU Ollama instance unreachable at http://localhost:11435: Connection refused
    Small chunks will fallback to GPU
```

Small chunks are routed to GPU instead. Processing continues normally.

### GPU Down (Fail Fast)
If the GPU instance becomes unavailable:
```
RuntimeError: GPU Ollama instance unavailable at http://localhost:11434.
GPU must be available for sharded mode (fail-fast policy).
Check if Ollama is running on GPU port.
```

The enricher exits immediately with an error. This is intentional: GPU is critical for large chunks, and quality matters more than uptime.

---

## Migration Guide: Enable Sharding Mid-Run

You can enable sharding after starting enrichment with a single instance. No re-processing of already-enriched chunks occurs.

### Scenario
1. Started enrichment with single Ollama instance
2. Current progress: 100/1000 chunks enriched (saved to `chunks.json`)
3. Want to enable GPU/CPU sharding for remaining 900 chunks

### Steps

**Step 1:** Stop enrichment (Ctrl+C)
```
Interruption: Saving already enriched chunks...
Save complete. Rerun script to resume.
```
Progress is auto-saved to `chunks.json` (100 chunks enriched).

**Step 2:** Start CPU Ollama on port 11435

**Terminal 2:**
```bash
OLLAMA_HOST=0.0.0.0:11435 OLLAMA_NUM_GPU=0 ollama pull ministral-3:8b
OLLAMA_HOST=0.0.0.0:11435 OLLAMA_NUM_GPU=0 ollama serve
```

**Step 3:** Enable sharding in `.env`

```bash
USE_LOCAL_SHARDING=true
OLLAMA_URL_GPU=http://localhost:11434
OLLAMA_URL_CPU=http://localhost:11435
ENRICHMENT_CHUNK_THRESHOLD=20
```

Or use command-line override instead:
```bash
python setup_enrich.py --enable-local-sharding
```

**Step 4:** Start both Ollama instances

**Terminal 1 (GPU):**
```bash
ollama serve
```

**Terminal 2 (CPU):**
```bash
OLLAMA_HOST=0.0.0.0:11435 OLLAMA_NUM_GPU=0 ollama serve
```

**Step 5:** Resume enrichment

**Terminal 3:**
```bash
python setup_enrich.py
```

### What Happens

The enricher automatically detects which chunks are already enriched:

```
1000 chunks loaded
100 chunks already enriched, 900 to process
[Enricher] GPU/CPU Sharding ENABLED
  GPU: http://localhost:11434
  CPU: http://localhost:11435
  Threshold: 20 messages
✓ GPU Ollama instance healthy at http://localhost:11434
✓ CPU Ollama instance healthy at http://localhost:11435

Enriching 900 chunks via OLLAMA...
```

Only the remaining 900 chunks are processed with GPU/CPU routing. The 100 already-enriched chunks are **not re-processed**.

**Why this works:**
- Enrichment filtering happens before provider initialization (see `setup_enrich.py:78`)
- Chunks with `narrative_summary` and `hypothetical_questions` are skipped
- Provider type (single, sharded, or MLX) doesn't affect filtering

---

## Troubleshooting

### Connection Errors
```
Traceback: requests.exceptions.ConnectionError: Connection to http://localhost:11435 refused
```

**Check:**
1. Is CPU instance running? `OLLAMA_HOST=0.0.0.0:11435 OLLAMA_NUM_GPU=0 ollama serve`
2. Is port 11435 in use by another process?
   ```bash
   lsof -i :11435
   ```
3. Is firewall blocking localhost connections?

### Port Conflicts
```
Error: listen tcp 0.0.0.0:11435: bind: address already in use
```

**Solution:** Kill existing Ollama processes or use different ports
```bash
# Find and kill Ollama processes
pkill -9 ollama

# Or use different ports
OLLAMA_HOST=0.0.0.0:11436 ollama serve  # CPU on 11436
```

### Model Mismatch
```
RuntimeError: Models differ between GPU and CPU instances
```

**Solution:** Ensure both instances have the same model
```bash
# Check GPU instance
curl http://localhost:11434/api/tags | jq '.models[].name'

# Check CPU instance
curl http://localhost:11435/api/tags | jq '.models[].name'

# Pull same model on both if needed
ollama pull ministral-3:8b
OLLAMA_HOST=0.0.0.0:11435 ollama pull ministral-3:8b
```

### Memory Issues
```
CUDA out of memory / CPU memory exhausted
```

**Solutions:**
- Reduce model size (use `ministral-3:3b` instead of `8b`)
- Close other applications to free RAM
- Increase OS swap space
- Use different machines (distributed enrichment)

---

## Performance Tuning

### Threshold Optimization

Measure speed with different thresholds:

```bash
# Test with threshold=15 (more GPU usage)
ENRICHMENT_CHUNK_THRESHOLD=15 python setup_enrich.py --limit 100

# Test with threshold=25 (more CPU usage)
ENRICHMENT_CHUNK_THRESHOLD=25 python setup_enrich.py --limit 100
```

**Profile results:**
- Watch GPU/CPU utilization during enrichment
- Monitor enrichment statistics at the end
- Choose threshold that maximizes throughput

### Model Selection

For faster enrichment with acceptable quality:
```bash
# .env
LLM_MODEL=ministral-3:3b
OLLAMA_URL_GPU=http://localhost:11434
OLLAMA_URL_CPU=http://localhost:11435
```

Fast models: `ministral-3:3b`, `neural-chat:7b-v3.1-q8_0`, `orca-mini:3b`
Strong models: `ministral-3:8b`, `mistral:latest`, `neural-chat:7b-v3.1-fp16`

---

## Advanced Usage

### Combining GPU/CPU Sharding with Distributed Enrichment

Run sharded enrichment on **multiple machines** with **local GPU/CPU sharding on each machine**:

```bash
# Machine 1 (processes shards 0, 2, 4, ... with GPU/CPU routing)
OLLAMA_URL_GPU=http://localhost:11434 \
OLLAMA_URL_CPU=http://localhost:11435 \
python setup_enrich.py --total-shards 3 --shard-index 0

# Machine 2 (processes shards 1, 3, 5, ... with GPU/CPU routing)
OLLAMA_URL_GPU=http://192.168.1.100:11434 \
OLLAMA_URL_CPU=http://192.168.1.100:11435 \
python setup_enrich.py --total-shards 3 --shard-index 1

# Machine 3 (processes shards 2, 4, 6, ... with GPU/CPU routing)
OLLAMA_URL_GPU=http://192.168.1.101:11434 \
OLLAMA_URL_CPU=http://192.168.1.101:11435 \
python setup_enrich.py --total-shards 3 --shard-index 2
```

After all shards complete:
```bash
python scripts/merge_enriched_shards.py
```

---

## Disabling Sharding

To revert to single-instance mode:

**Option 1: Via configuration**
1. Disable in `.env`:
   ```bash
   USE_LOCAL_SHARDING=false
   ```

2. Kill CPU instance (Terminal 2)
   ```bash
   Ctrl+C
   ```

3. Resume enrichment (uses single GPU instance)
   ```bash
   python setup_enrich.py
   ```

**Option 2: Via command-line (temporary override)**
```bash
python setup_enrich.py --disable-local-sharding
```

Already-enriched chunks are preserved. Only remaining chunks use single-instance routing.

---

## Statistics

At the end of enrichment with sharding enabled, statistics show routing distribution:

```
📊 Sharding Statistics:
   GPU routed: 15234
   CPU routed: 17325
   CPU→GPU fallback: 12
   Errors: 0
   GPU utilization: 46.8%
```

- **GPU routed:** Chunks with ≥threshold messages processed on GPU
- **CPU routed:** Chunks with <threshold messages processed on CPU
- **CPU→GPU fallback:** Small chunks routed to GPU because CPU was unavailable
- **Errors:** Failed enrichments (rare, indicates model or instance issues)
- **GPU utilization:** Percentage of requests routed to GPU

---

## Design Rationale

**Why enrichment only?**
- Enrichment is the bottleneck (90+ hours for large datasets)
- Chat/summarization need consistent low latency (always GPU)
- Non-user-facing workload allows mixed backends

**Why message count routing?**
- Already available in `Chunk.message_count` (zero overhead)
- Strong correlation with enrichment complexity
- Simple threshold logic (no ML or profiling needed)

**Why asymmetric failover?**
- CPU→GPU is safe: GPU handles all chunk sizes well
- GPU→CPU is blocked: Would produce inconsistent quality
- Better to fail fast than produce low-quality enrichment

**Why same model on both instances?**
- Ensures consistent output quality across shards
- Simplifies debugging (no "which instance produced this" questions)
- Faster migration: pulling one model instead of managing different ones

---

## See Also

- [AGENTS.md](../AGENTS.md) - Enricher agent details
- [RAG_PIPELINE.md](docs/RAG_PIPELINE.md) - Enrichment in the RAG pipeline
- [DEVELOPMENT.md](docs/DEVELOPMENT.md) - Development workflow
