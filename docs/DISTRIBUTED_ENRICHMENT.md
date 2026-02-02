# Distributed Enrichment Guide

## Overview

This guide explains how to speed up the enrichment process by distributing the workload across multiple machines using shard-based parallel processing.

**Problem:** The enrichment process is CPU-intensive and can take several days on a single machine (32,559 chunks × ~10 seconds per chunk ≈ several days).

**Solution:** Split the chunks into independent shards, process each on a separate machine, then merge the results.

## Architecture

### Race Condition Prevention

The original implementation had a critical issue: each process would load all chunks, enrich its subset, then save **all** chunks back, causing the last writer to overwrite the other's work.

**Our solution:** Each machine writes to its own file:
- Machine 1 → `chunks_shard0.json`
- Machine 2 → `chunks_shard1.json`
- After both complete → merge into `chunks.json`

This eliminates race conditions and allows safe error recovery.

### Sharding Logic

Chunks are distributed using a simple modulo approach:
```python
# Machine with shard_index processes chunks where:
chunk_index % total_shards == shard_index
```

For 2 machines:
- Shard 0: chunks 0, 2, 4, 6, ... (odd indices)
- Shard 1: chunks 1, 3, 5, 7, ... (even indices)

## Quick Start (2 Machines)

### Phase 1: Prepare

**On Machine 1** (or wherever you have the initial chunks):
```bash
# Ensure chunks.json exists
python setup_chunks.py

# Copy to Machine 2
scp rag_data/chunks.json user@machine2:~/instagram-assistant/rag_data/
```

### Phase 2: Parallel Enrichment

**On Machine 1** (Terminal/Session):
```bash
python setup_enrich.py --total-shards 2 --shard-index 0
# Processes chunks 0, 2, 4, 6...
# Saves to: rag_data/chunks_shard0.json
# Logs to: enrichment_shard0.log
```

**On Machine 2** (Terminal/Session):
```bash
python setup_enrich.py --total-shards 2 --shard-index 1
# Processes chunks 1, 3, 5, 7...
# Saves to: rag_data/chunks_shard1.json
# Logs to: enrichment_shard1.log
```

**Monitor progress:**
```bash
# On Machine 1
tail -f enrichment_shard0.log

# On Machine 2
tail -f enrichment_shard1.log

# Or from Machine 1, check shard file growth
ls -lh rag_data/chunks_shard*.json
```

### Phase 3: Merge Results

Once **both** shards complete enrichment:

**On Machine 1:**
```bash
# Copy shard 1 results from Machine 2
scp user@machine2:~/instagram-assistant/rag_data/chunks_shard1.json ./rag_data/

# Merge shards
python scripts/merge_enriched_shards.py

# Verify all chunks enriched
python scripts/check_enrichment_status.py

# Continue pipeline
python setup_embeddings.py
```

## Monitoring Progress

### Check Status During Enrichment

```bash
# Show shard file status (during enrichment)
python scripts/check_enrichment_status.py --show-shards

# Sample output:
# 🔀 Distributed enrichment in progress (shard files detected):
#   Shard 0: 1234/15000 enriched (8.2%) - 45.3 MB
#   Shard 1: 2100/15000 enriched (14.0%) - 67.2 MB
```

### Check Final Status After Merge

```bash
python scripts/check_enrichment_status.py

# Shows overall enrichment percentage and per-conversation breakdown
```

## Advanced Configuration

### 3+ Machines

Example with 3 machines:

**Machine 1:**
```bash
python setup_enrich.py --total-shards 3 --shard-index 0
# Processes chunks 0, 3, 6, 9, ...
```

**Machine 2:**
```bash
python setup_enrich.py --total-shards 3 --shard-index 1
# Processes chunks 1, 4, 7, 10, ...
```

**Machine 3:**
```bash
python setup_enrich.py --total-shards 3 --shard-index 2
# Processes chunks 2, 5, 8, 11, ...
```

Then merge as usual:
```bash
# Copy all shard files to one machine
scp user@machine2:~/instagram-assistant/rag_data/chunks_shard1.json ./rag_data/
scp user@machine3:~/instagram-assistant/rag_data/chunks_shard2.json ./rag_data/

python scripts/merge_enriched_shards.py
```

### LLM Model Configuration

To use a specific model or provider:

```bash
# Use Ollama with custom model
python setup_enrich.py --total-shards 2 --shard-index 0 --model mistral:latest

# Use MLX provider
python setup_enrich.py --total-shards 2 --shard-index 0 --provider mlx --model model-name
```

### Resume Interrupted Enrichment

If enrichment is interrupted on a shard, simply rerun the same command. It will:
1. Load the partial shard file
2. Resume from the last saved checkpoint (every 20 chunks)
3. Continue until all chunks are enriched

```bash
# On Machine 1, after interruption
python setup_enrich.py --total-shards 2 --shard-index 0
# Automatically resumes from checkpoint
```

## Merge Options

### Preview Merge (Dry Run)

```bash
python scripts/merge_enriched_shards.py --dry-run
# Shows what would be merged without writing
```

### Detailed Merge Log

```bash
python scripts/merge_enriched_shards.py --verbose
# Shows progress on each shard file
```

### Custom Data Directory

```bash
python scripts/merge_enriched_shards.py --data-dir /path/to/data
```

## Error Recovery

### One Shard Fails Mid-Enrichment

**Scenario:** Machine 2 crashes, Machine 1 is still enriching.

**Recovery:**
1. The other machine's work is safe in its shard file
2. Restart Machine 2
3. Rerun the same enrichment command (it resumes from checkpoint)
4. When complete, merge as usual

### Merge Fails

**Scenario:** `merge_enriched_shards.py` encounters an error

**Recovery:**
1. An automatic backup is created: `chunks.json.backup.YYYYMMDD_HHMMSS`
2. The original `chunks.json` is not overwritten
3. Fix the issue and retry:
   ```bash
   python scripts/merge_enriched_shards.py
   ```

The merge is idempotent—running it multiple times is safe.

### Wrong Shard Index Used

**Scenario:** You accidentally ran both machines with shard-index 0

**Detection & Recovery:**
1. The merge script will detect the conflict
2. Manually delete the incorrect shard file
3. Rerun the enrichment on the correct machine
4. Then merge again

## Performance Expectations

### Single Machine
- **Chunks:** 32,559
- **Time per chunk:** ~10 seconds
- **Total time:** ~32k chunks × 10s ≈ 3-4 days
- **Memory:** ~2GB (all chunks loaded)

### 2 Machines
- **Chunks per machine:** ~16,280
- **Time per chunk:** ~10 seconds (unchanged)
- **Total time:** ~16k chunks × 10s ≈ 1.5-2 days (parallel)
- **Memory per machine:** ~1GB (only shard chunks loaded)
- **Speedup:** ~2x (linear, no coordination overhead)

### 4 Machines
- **Chunks per machine:** ~8,140
- **Total time:** ~8k chunks × 10s ≈ 0.8-1 day (parallel)
- **Speedup:** ~4x

## Verification Checklist

### Before Starting
- [ ] `chunks.json` exists on both machines
- [ ] Both machines have same `chunks.json` (compare file sizes)
- [ ] Ollama/MLX LLM is running on both machines with same model
- [ ] Both machines have sufficient disk space (each shard ≈ 100-200 MB)

### During Enrichment
- [ ] Both enrichment scripts show progress (5+ chunks/second)
- [ ] Log files (`enrichment_shard*.log`) are growing
- [ ] Shard files are growing (`ls -lh rag_data/chunks_shard*.json`)
- [ ] No error messages in logs (check with `tail -f`)

### After Enrichment
- [ ] Both shard files exist and have reasonable size
- [ ] Both enrichment scripts completed successfully
- [ ] Run `check_enrichment_status.py` to verify both shards are complete

### After Merge
- [ ] `python scripts/check_enrichment_status.py` shows 100% enriched
- [ ] Chunk count unchanged: `wc -l rag_data/chunks.json`
- [ ] Backup file created: `ls -l rag_data/chunks.json.backup.*`
- [ ] Test with CLI: `python cli.py` and run a query

## Troubleshooting

### "Conflict detected: Different enrichment in multiple shards"

This warning appears if the same chunk was enriched differently on different machines. This shouldn't happen in normal operation. Solutions:

1. **Delete the incorrect shard and re-enrich:**
   ```bash
   rm rag_data/chunks_shard1.json
   # Re-run enrichment on machine 2
   python setup_enrich.py --total-shards 2 --shard-index 1
   ```

2. **Proceed with merge (uses first enrichment found):**
   ```bash
   python scripts/merge_enriched_shards.py
   # Merge script will warn but continue
   ```

### Memory Usage Too High

If a shard process uses too much memory:

1. Reduce other applications on that machine
2. The script optimizes memory by keeping only the shard's chunks (not all chunks)
3. Monitor with: `top` or `ps aux | grep setup_enrich`

### LLM Model Mismatch Between Machines

If different models are used on different machines:

```bash
# Machine 1
python setup_enrich.py --total-shards 2 --shard-index 0 --model mistral:latest

# Machine 2
python setup_enrich.py --total-shards 2 --shard-index 1 --model mistral:latest
# Must use SAME model
```

The enrichment quality will vary by model. Ensure both machines use the same model.

### No Shard Files Generated

If `chunks_shard0.json` and `chunks_shard1.json` don't exist:

1. Check enrichment completed: `tail -f enrichment_shard*.log`
2. Verify chunks were actually enriched (not already complete)
3. Check disk space: `df -h rag_data/`
4. Check file permissions: `ls -l rag_data/`

## CLI Commands Reference

```bash
# Setup/Enrichment
python setup_enrich.py --total-shards 2 --shard-index 0      # Shard mode
python setup_enrich.py --reset --total-shards 2 --shard-index 0  # Re-enrich shard
python setup_enrich.py --model mistral:latest --total-shards 2 --shard-index 0  # Custom model

# Merging
python scripts/merge_enriched_shards.py                # Auto-merge all shards
python scripts/merge_enriched_shards.py --dry-run      # Preview
python scripts/merge_enriched_shards.py --verbose      # Detailed log

# Monitoring
python scripts/check_enrichment_status.py              # Overall status
python scripts/check_enrichment_status.py --show-shards  # Shard progress
python scripts/check_enrichment_status.py --detailed   # Per-conversation

# Logging
tail -f enrichment_shard0.log                         # Watch machine 1
tail -f enrichment_shard1.log                         # Watch machine 2
grep -i error enrichment_shard*.log                   # Find errors
```

## Files Modified/Created

### Core Implementation
- **`rag_pipeline/chunker.py`** - Added `shard_index` parameter to `save_chunks()`
- **`setup_enrich.py`** - Integrated shard mode with memory optimization and log files

### New Scripts
- **`scripts/merge_enriched_shards.py`** - Merge shard files with validation and error recovery
- **`scripts/check_enrichment_status.py`** (enhanced) - Added `--show-shards` option

### Documentation
- **`docs/COMMANDS.md`** (updated) - Added distributed enrichment section
- **`docs/DISTRIBUTED_ENRICHMENT.md`** (this file) - Comprehensive guide

## Performance Tips

1. **Network:** Use fast network or `rsync` for shard file transfer
   ```bash
   rsync -avz rag_data/chunks.json user@machine2:~/instagram-assistant/rag_data/
   ```

2. **Disk:** SSD recommended for faster JSON I/O

3. **CPU:** Use same or similar CPU machines for predictable speed

4. **LLM:** Ensure Ollama/MLX is optimized with GPU if available

5. **Monitoring:** Check system resources during enrichment
   ```bash
   top                           # CPU/Memory
   iotop                         # Disk I/O
   watch 'tail -1 enrichment_shard0.log'  # Progress
   ```

## FAQ

**Q: Can I use 10 machines?**
A: Yes, but with diminishing returns. Network overhead increases. Recommended maximum: 4-8 machines.

**Q: What if one machine is much slower?**
A: The merge will wait for all shards. Consider assigning fewer chunks to slower machines:
```bash
# Slow machine: larger shard
# Fast machine: smaller shard
# (Still uses modulo distribution, but speeds things up)
```

**Q: Can I pause and resume?**
A: Yes. The script saves every 20 chunks and resumes from the checkpoint on restart.

**Q: Do I need to start at the same time?**
A: No, machines can start enrichment at different times. Just ensure they process different shards.

**Q: What about very large chunk numbers (100k+)?**
A: The approach scales linearly. Add more machines as needed. Merge time is O(n) but very fast.

**Q: Can I use cloud instances?**
A: Yes, just ensure they have access to the chunks.json file and can download the LLM model.

## Next Steps

After successful merge and enrichment:

1. **Verify quality:** `python cli.py` and test search
2. **Continue pipeline:** `python setup_embeddings.py`
3. **Clean up:** `rm rag_data/chunks_shard*.json` (optional, can keep for debugging)
4. **Backup:** `cp rag_data/chunks.json rag_data/chunks.json.enriched`
