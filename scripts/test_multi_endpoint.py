#!/usr/bin/env python3
"""
Test script for multi-endpoint Ollama functionality.

This script tests the multi-endpoint provider with 10 random unenriched chunks.

Usage:
    # Single endpoint test (default):
    python scripts/test_multi_endpoint.py
    
    # Multi-endpoint test:
    OLLAMA_ENDPOINTS="http://localhost:11434,http://192.168.1.16:11434" python scripts/test_multi_endpoint.py
"""
import sys
import random
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from rag_pipeline.core.config import Config
from rag_pipeline.indexing.chunker import ConversationChunker
from rag_pipeline.enrichment.enricher import ChunkEnricher


def main():
    config = Config()
    
    print("=" * 60)
    print("🧪 MULTI-ENDPOINT OLLAMA TEST")
    print("=" * 60)
    
    # Show endpoint configuration
    print(f"\n📍 Configured endpoints: {len(config.ollama_endpoints)}")
    for i, ep in enumerate(config.ollama_endpoints):
        print(f"   {i+1}. {ep}")
    
    # Load chunks
    print("\n📦 Loading chunks...")
    chunker = ConversationChunker(config)
    
    if not config.chunks_cache_path.exists():
        print("❌ No chunks found. Run setup_chunks.py first.")
        sys.exit(1)
    
    chunks = chunker.load_chunks()
    print(f"   Loaded {len(chunks)} chunks")
    
    # Find unenriched chunks
    unenriched = [c for c in chunks if not c.narrative_summary or not c.hypothetical_questions]
    print(f"   Found {len(unenriched)} unenriched chunks")
    
    if len(unenriched) == 0:
        print("   ⚠️ All chunks are already enriched. Using random enriched chunks for test.")
        test_chunks = random.sample(chunks, min(10, len(chunks)))
    else:
        # Select 10 random unenriched chunks
        test_chunks = random.sample(unenriched, min(10, len(unenriched)))
    
    print(f"   Selected {len(test_chunks)} chunks for testing")
    
    # Create enricher and test
    print(f"\n🔧 Testing enrichment with {config.llm_model}...")
    enricher = ChunkEnricher(config, provider="ollama")
    
    success_count = 0
    for i, chunk in enumerate(test_chunks):
        try:
            print(f"\r   Processing chunk {i+1}/{len(test_chunks)}: {chunk.chunk_id[:30]}...", end="")
            result = enricher.enrich_chunk(chunk)
            if result and result[0]:  # Check if narrative_summary exists
                success_count += 1
        except Exception as e:
            print(f"\n   ❌ Error on chunk {chunk.chunk_id}: {e}")
    
    print(f"\n\n✅ Enrichment test complete: {success_count}/{len(test_chunks)} successful")
    
    # Print distribution stats if available
    if hasattr(enricher, 'model_manager') and hasattr(enricher.model_manager, '_multi_provider'):
        provider = enricher.model_manager._multi_provider
        if provider:
            provider.print_stats()
    
    print("=" * 60)
    return success_count == len(test_chunks)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
