#!/usr/bin/env python3
"""
Step 3: Generating embeddings with Content-Hash Caching.
"""
import sys
import time
import argparse
import hashlib
import json
import numpy as np
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from rag_pipeline.core.config import Config
from rag_pipeline.indexing.chunker import ConversationChunker
from rag_pipeline.core.models import Chunk
from rag_pipeline.indexing.embeddings import EmbeddingModel, get_chunk_embedding_text
from rag_pipeline.utils.cli_utils import (
    print_header,
    CHECKPOINT_DIR,
    DEFAULT_BATCH_SIZE,
    get_checkpoint_path,
    reset_checkpoints,
)

EMBEDDINGS_CACHE_DIR = Path("rag_data/embeddings_cache")

def get_content_hash(text: str) -> str:
    """Returns MD5 hash of the text."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def run(config: Config, reset: bool = False, batch_size: int = DEFAULT_BATCH_SIZE, enriched_only: bool = False) -> np.ndarray:
    print_header("Generating embeddings (Content-Hash Cache)", step="3/8")

    chunker = ConversationChunker(config)
    if not config.chunks_cache_path.exists():
        print("Error: No chunks found. Run setup_chunks.py first")
        return None

    all_chunks = chunker.load_chunks()
    
    # Filter: Keep only chunks that have enrichment if requested
    if enriched_only:
        chunks = [c for c in all_chunks if c.narrative_summary and c.hypothetical_questions]
        print(f"Filter: {len(chunks)} enriched chunks found (out of {len(all_chunks)})")
    else:
        chunks = all_chunks
        print(f"Processing all {len(chunks)} chunks")
    
    # Log chunks that failed enrichment (they'll use raw content only)
    failed_chunks = [c for c in chunks if getattr(c, 'enrichment_failed', False)]
    if failed_chunks:
        print(f"ℹ️ {len(failed_chunks)} chunks failed enrichment - using raw content only")

    if not chunks:
        print("No chunks to process.")
        return None

    if reset and EMBEDDINGS_CACHE_DIR.exists():
        import shutil
        shutil.rmtree(EMBEDDINGS_CACHE_DIR)
        print("Cache cleared.")

    EMBEDDINGS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Check cache for each chunk
    to_process = []
    chunk_hashes = [] # To keep track of which hash corresponds to which chunk index

    for chunk in chunks:
        text = get_chunk_embedding_text(chunk)
        h = get_content_hash(text)
        chunk_hashes.append(h)
        
        cache_path = EMBEDDINGS_CACHE_DIR / f"{h}.npy"
        if not cache_path.exists():
            to_process.append((chunk, h))

    if not to_process:
        print("✅ All embeddings are already in cache.")
    else:
        print(f"🚀 {len(to_process)} embeddings need to be generated.")
        embedding_model = EmbeddingModel(config)
        n_batches = (len(to_process) + batch_size - 1) // batch_size
        
        for i in range(n_batches):
            batch_data = to_process[i*batch_size : (i+1)*batch_size]
            print(f"Batch {i+1}/{n_batches} ({len(batch_data)} chunks)...")
            
            texts = [get_chunk_embedding_text(item[0]) for item in batch_data]
            vectors = embedding_model.encode(texts, show_progress=True)
            
            for (chunk, h), vec in zip(batch_data, vectors):
                np.save(EMBEDDINGS_CACHE_DIR / f"{h}.npy", vec)

    # 2. Consolidation & Map Save
    print("\nConsolidating embeddings matrix...")
    all_vectors = []
    for h in chunk_hashes:
        all_vectors.append(np.load(EMBEDDINGS_CACHE_DIR / f"{h}.npy"))
    
    embeddings = np.vstack(all_vectors)

    # 3. Save the specific subset of bits used for this index
    # This allows step 4 (indexing) to know EXACTLY which chunks match these embeddings
    indexed_chunks_path = Path("rag_data/chunks_indexed.json")
    with open(indexed_chunks_path, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in chunks], f, ensure_ascii=False, indent=2)
    print(f"Done! Saved {len(chunks)} chunk definitions to {indexed_chunks_path}")

    # Compatibility Save
    reset_checkpoints(CHECKPOINT_DIR)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(get_checkpoint_path(0, CHECKPOINT_DIR), embeddings)
    
    # Print summary if we generated any embeddings
    if 'embedding_model' in locals():
        embedding_model.logger.export_csv()
        embedding_model.logger.print_summary()
    
    return embeddings

def main():
    parser = argparse.ArgumentParser(description="Step 3: Embeddings with Hash Cache")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--enriched-only", action="store_true", help="Only embed enriched chunks")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--cpu", action="store_true", help="Force CPU usage (ignore GPU/MPS)")
    args = parser.parse_args()
    
    config = Config()
    if args.cpu:
        config.use_gpu = False
        
    embeddings = run(config, reset=args.reset, batch_size=args.batch_size, enriched_only=args.enriched_only)
    sys.exit(0 if embeddings is not None else 1)

if __name__ == "__main__":
    main()