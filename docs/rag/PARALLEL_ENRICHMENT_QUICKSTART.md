# Parallel Enrichment - Quick Start

## 30-Second Summary

Run enrichment on multiple machines simultaneously to speed up processing by ~2x-4x.

```bash
# Machine 1
python setup_enrich.py --total-shards 2 --shard-index 0

# Machine 2
python setup_enrich.py --total-shards 2 --shard-index 1

# After both finish
python scripts/merge_enriched_shards.py
```

## Setup (2 Minutes)

### 1. Copy chunks to all machines
```bash
# From machine 1 to machine 2
scp rag_data/chunks.json user@machine2:~/sira/rag_data/
```

### 2. Ensure Ollama/LLM is running
Both machines need the same LLM model:
```bash
ollama pull mistral  # or your preferred model
ollama serve         # in background
```

## Run (Days)

### 1. Start enrichment on Machine 1
```bash
python setup_enrich.py --total-shards 2 --shard-index 0
```

### 2. Start enrichment on Machine 2
```bash
python setup_enrich.py --total-shards 2 --shard-index 1
```

### 3. Monitor (optional)
```bash
# Watch logs
tail -f enrichment_shard0.log  # on machine 1
tail -f enrichment_shard1.log  # on machine 2

# Check progress
python scripts/check_enrichment_status.py --show-shards
```

## Finish (1 Minute)

### 1. Copy shard files to one machine
```bash
scp user@machine2:~/sira/rag_data/chunks_shard1.json ./rag_data/
```

### 2. Merge shards
```bash
python scripts/merge_enriched_shards.py
```

### 3. Verify
```bash
python scripts/check_enrichment_status.py
# Should show 100% enriched
```

### 4. Continue pipeline
```bash
python setup_embeddings.py
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No chunks found" | Run `python setup_chunks.py` first |
| Different files on machines | Use `scp` to copy chunks.json to both |
| Different LLM models | Both machines must use `--model mistral:latest` (or same model) |
| One machine crashes | Restart it, rerun same command, it resumes from checkpoint |
| Merge fails | Check `chunks.json.backup.*` was created, try again |
| Memory too high | The script optimizes by keeping only shard chunks |

## Files

**Created:**
- `scripts/merge_enriched_shards.py` - Merge shard files
- `docs/DISTRIBUTED_ENRICHMENT.md` - Detailed guide

**Modified:**
- `rag_pipeline/indexing/chunker.py` - Added shard support
- `setup_enrich.py` - Integrated distributed mode
- `scripts/check_enrichment_status.py` - Added `--show-shards`
- `docs/COMMANDS.md` - Updated with new commands

## Performance

| Setup | Time | Speedup |
|-------|------|---------|
| 1 machine | 3-4 days | - |
| 2 machines | 1.5-2 days | 2x |
| 4 machines | 0.8-1 day | 4x |

## Key Points

✓ **No race conditions** - Each machine writes to its own file
✓ **Safe resumable** - Crashes don't lose the other machine's work
✓ **Memory optimized** - Only relevant chunks in memory per machine
✓ **Simple merge** - Auto-detects shards and merges with validation
✓ **Backward compatible** - Original single-machine mode still works

## Examples

### 3 machines
```bash
# Machine 1
python setup_enrich.py --total-shards 3 --shard-index 0

# Machine 2
python setup_enrich.py --total-shards 3 --shard-index 1

# Machine 3
python setup_enrich.py --total-shards 3 --shard-index 2

# Then merge (copy all shard files first)
python scripts/merge_enriched_shards.py
```

### Custom model
```bash
python setup_enrich.py --total-shards 2 --shard-index 0 --model mistral:latest
```

### Preview merge (dry-run)
```bash
python scripts/merge_enriched_shards.py --dry-run
# Shows what would happen without writing
```

### Detailed monitoring
```bash
python scripts/merge_enriched_shards.py --verbose
# Shows progress on each shard
```

## For More Details

See `docs/DISTRIBUTED_ENRICHMENT.md` for:
- Architecture and design decisions
- Error recovery procedures
- Advanced configurations
- Performance tips
- FAQ and troubleshooting
