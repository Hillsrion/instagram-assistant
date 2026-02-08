#!/usr/bin/env python3
"""
Statistical analysis script for RAG data.
Displays detailed metrics on conversations, messages, and chunks.

Usage:
    python3 rag_stats.py
"""
import sys
import time
from pathlib import Path
from statistics import mean, median

# Add parent folder to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.core.config import Config
from rag_pipeline.indexing.chunker import ConversationChunker
from rag_pipeline.core.models import Chunk

def format_number(n):
    return f"{n:,}".replace(",", " ")

def main():
    config = Config()
    chunker = ConversationChunker(config)
    
    print("=" * 60)
    print("📊 RAG DATA ANALYSIS")
    print("=" * 60)
    
    print(f"\n📂 Conversations directory: {config.conversations_dir}")
    
    if not config.conversations_dir.exists():
        print("❌ Conversations directory does not exist.")
        return

    # 1. Source files analysis
    print("\n🔍 Analyzing source files...")
    
    files = list(config.conversations_dir.glob('*.txt'))
    total_conversations = len(files)
    
    if total_conversations == 0:
        print("⚠️  No conversations found (.txt).")
        return

    total_messages = 0
    total_media = 0
    total_links = 0
    
    messages_per_conv = []
    
    start_time = time.time()
    
    for i, file_path in enumerate(files):
        try:
            # Use chunker parser
            _, messages = chunker.parse_conversation(file_path)
            
            count = len(messages)
            messages_per_conv.append(count)
            total_messages += count
            
            # Detailed stats
            for msg in messages:
                if msg.has_media:
                    if msg.media_type == 'link':
                        total_links += 1
                    else:
                        total_media += 1
                        
            # Simple progress bar
            if (i + 1) % 10 == 0:
                sys.stdout.write(f"\r   Processing: {i + 1}/{total_conversations}")
                sys.stdout.flush()
                
        except Exception as e:
            print(f"\n⚠️  Error on {file_path.name}: {e}")

    sys.stdout.write(f"\r   Processing: {total_conversations}/{total_conversations}\n")
    elapsed = time.time() - start_time
    
    # 2. Chunk analysis (if available)
    print("\n📦 Analyzing chunks...")
    chunks = chunker.load_chunks()
    total_chunks = len(chunks)
    
    # 3. Display results
    print("\n" + "=" * 60)
    print("📈 GLOBAL RESULTS")
    print("=" * 60)
    
    col_width = 25
    
    print(f"\n1️⃣  CONVERSATIONS")
    print(f"   • {'Total':<{col_width}}: {format_number(total_conversations)}")
    if messages_per_conv:
        print(f"   • {'Avg msgs/conv':<{col_width}}: {mean(messages_per_conv):.1f}")
        print(f"   • {'Median msgs/conv':<{col_width}}: {median(messages_per_conv):.1f}")
        print(f"   • {'Max msgs/conv':<{col_width}}: {format_number(max(messages_per_conv))}")
        print(f"   • {'Min msgs/conv':<{col_width}}: {format_number(min(messages_per_conv))}")

    print(f"\n2️⃣  MESSAGES & CONTENT")
    print(f"   • {'Total messages':<{col_width}}: {format_number(total_messages)}")
    print(f"   • {'Total media':<{col_width}}: {format_number(total_media)}")
    print(f"   • {'Total links':<{col_width}}: {format_number(total_links))}")
    
    print(f"\n3️⃣  CHUNKS (Indexing units)")
    if total_chunks > 0:
        print(f"   • {'Total chunks':<{col_width}}: {format_number(total_chunks)}")
        print(f"   • {'Ratio msgs/chunk':<{col_width}}: {total_messages / total_chunks:.1f}")
        print(f"   • {'Ratio chunks/conv':<{col_width}}: {total_chunks / total_conversations:.1f}")
        
        # Enrichment stats
        enriched_count = sum(1 for c in chunks if c.narrative_summary or c.hypothetical_questions)
        print(f"   • {'Enriched chunks (LLM)':<{col_width}}: {format_number(enriched_count)} ({enriched_count/total_chunks*100:.1f}%)")
    else:
        print(f"   • {'Total chunks':<{col_width}}: 0 (Not generated or cache empty)")
        print("     💡 Run 'python3 setup_rag_batch.py' to generate chunks.")

    print("\n" + "=" * 60)
    print(f"⏱️  Analysis time: {elapsed:.2f}s")
    print("=" * 60)

if __name__ == "__main__":
    main()