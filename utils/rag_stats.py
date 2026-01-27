#!/usr/bin/env python3
"""
Script d'analyse statistique des données RAG.
Affiche des métriques détaillées sur les conversations, messages et chunks.

Usage:
    python3 rag_stats.py
"""
import sys
import time
from pathlib import Path
from statistics import mean, median

# Ajout du dossier parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker

def format_number(n):
    return f"{n:,}".replace(",", " ")

def main():
    config = Config()
    chunker = ConversationChunker(config)
    
    print("=" * 60)
    print("📊 ANALYSE DES DONNÉES RAG")
    print("=" * 60)
    
    print(f"\n📂 Dossier conversations : {config.conversations_dir}")
    
    if not config.conversations_dir.exists():
        print("❌ Le dossier de conversations n'existe pas.")
        return

    # 1. Analyse des fichiers sources
    print("\n🔍 Analyse des fichiers sources en cours...")
    
    files = list(config.conversations_dir.glob('*.txt'))
    total_conversations = len(files)
    
    if total_conversations == 0:
        print("⚠️  Aucune conversation trouvée (.txt).")
        return

    total_messages = 0
    total_media = 0
    total_links = 0
    
    messages_per_conv = []
    
    start_time = time.time()
    
    for i, file_path in enumerate(files):
        try:
            # On utilise le parser du chunker
            _, messages = chunker.parse_conversation(file_path)
            
            count = len(messages)
            messages_per_conv.append(count)
            total_messages += count
            
            # Stats détaillées
            for msg in messages:
                if msg.has_media:
                    if msg.media_type == 'link':
                        total_links += 1
                    else:
                        total_media += 1
                        
            # Barre de progression simple
            if (i + 1) % 10 == 0:
                sys.stdout.write(f"\r   Traitement : {i + 1}/{total_conversations}")
                sys.stdout.flush()
                
        except Exception as e:
            print(f"\n⚠️  Erreur sur {file_path.name}: {e}")

    sys.stdout.write(f"\r   Traitement : {total_conversations}/{total_conversations}\n")
    elapsed = time.time() - start_time
    
    # 2. Analyse des chunks (si disponibles)
    print("\n📦 Analyse des chunks...")
    chunks = chunker.load_chunks()
    total_chunks = len(chunks)
    
    # 3. Affichage des résultats
    print("\n" + "=" * 60)
    print("📈 RÉSULTATS GLOBAUX")
    print("=" * 60)
    
    col_width = 25
    
    print(f"\n1️⃣  CONVERSATIONS")
    print(f"   • {'Total':<{col_width}}: {format_number(total_conversations)}")
    if messages_per_conv:
        print(f"   • {'Moyenne msgs/conv':<{col_width}}: {mean(messages_per_conv):.1f}")
        print(f"   • {'Médiane msgs/conv':<{col_width}}: {median(messages_per_conv):.1f}")
        print(f"   • {'Max msgs/conv':<{col_width}}: {format_number(max(messages_per_conv))}")
        print(f"   • {'Min msgs/conv':<{col_width}}: {format_number(min(messages_per_conv))}")

    print(f"\n2️⃣  MESSAGES & CONTENU")
    print(f"   • {'Total messages':<{col_width}}: {format_number(total_messages)}")
    print(f"   • {'Total médias':<{col_width}}: {format_number(total_media)}")
    print(f"   • {'Total liens':<{col_width}}: {format_number(total_links)}")
    
    print(f"\n3️⃣  CHUNKS (Unités d'indexation)")
    if total_chunks > 0:
        print(f"   • {'Total chunks':<{col_width}}: {format_number(total_chunks)}")
        print(f"   • {'Ratio msgs/chunk':<{col_width}}: {total_messages / total_chunks:.1f}")
        print(f"   • {'Ratio chunks/conv':<{col_width}}: {total_chunks / total_conversations:.1f}")
        
        # Stats d'enrichissement
        enriched_count = sum(1 for c in chunks if c.narrative_summary or c.hypothetical_questions)
        print(f"   • {'Chunks enrichis (LLM)':<{col_width}}: {format_number(enriched_count)} ({enriched_count/total_chunks*100:.1f}%)")
    else:
        print(f"   • {'Total chunks':<{col_width}}: 0 (Non générés ou cache vide)")
        print("     💡 Lancez 'python3 setup_rag_batch.py' pour générer les chunks.")

    print("\n" + "=" * 60)
    print(f"⏱️  Temps d'analyse : {elapsed:.2f}s")
    print("=" * 60)

if __name__ == "__main__":
    main()
