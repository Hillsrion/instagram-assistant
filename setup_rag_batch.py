#!/usr/bin/env python3
"""
Script d'indexation RAG avec BATCHING et REPRISE.
Permet de générer les embeddings de manière incrémentale avec checkpoints.

Usage:
    python3 setup_rag_batch.py              # Lance/reprend l'indexation
    python3 setup_rag_batch.py --reset      # Repart de zéro
    python3 setup_rag_batch.py --status     # Affiche l'état actuel
"""
import sys
import time
import argparse
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker, Chunk
from rag_pipeline.embeddings import EmbeddingModel
from rag_pipeline.vector_store import VectorStore


# Configuration du batching
BATCH_SIZE = 500  # Chunks par batch
CHECKPOINT_DIR = Path("rag_data/checkpoints")


def get_checkpoint_path(batch_idx: int) -> Path:
    """Retourne le chemin du fichier checkpoint pour un batch."""
    return CHECKPOINT_DIR / f"embeddings_batch_{batch_idx:04d}.npy"


def count_existing_checkpoints() -> int:
    """Compte le nombre de checkpoints existants."""
    if not CHECKPOINT_DIR.exists():
        return 0
    return len(list(CHECKPOINT_DIR.glob("embeddings_batch_*.npy")))


def count_existing_embeddings() -> int:
    """Compte le nombre réel d'embeddings dans les checkpoints."""
    if not CHECKPOINT_DIR.exists():
        return 0

    total = 0
    for f in sorted(CHECKPOINT_DIR.glob("embeddings_batch_*.npy")):
        emb = np.load(f)
        total += len(emb)
    return total


def load_all_checkpoints() -> np.ndarray:
    """Charge et concatène tous les checkpoints."""
    if not CHECKPOINT_DIR.exists():
        return None

    checkpoint_files = sorted(CHECKPOINT_DIR.glob("embeddings_batch_*.npy"))
    if not checkpoint_files:
        return None

    print(f"   Chargement de {len(checkpoint_files)} checkpoints...")
    embeddings_list = []
    for f in checkpoint_files:
        emb = np.load(f)
        embeddings_list.append(emb)
        print(f"   ✓ {f.name}: {len(emb)} embeddings")

    return np.vstack(embeddings_list)


def show_status(config: Config):
    """Affiche l'état actuel de l'indexation."""
    print("=" * 60)
    print("STATUS - RAG Pipeline")
    print("=" * 60)

    # Chunks
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks()
    print(f"\n📝 Chunks: {len(chunks)} (dans {config.chunks_cache_path})")

    # Checkpoints
    n_checkpoints = count_existing_checkpoints()
    chunks_processed = n_checkpoints * BATCH_SIZE
    print(f"\n🧠 Embeddings:")
    print(f"   • Checkpoints: {n_checkpoints}")
    print(f"   • Chunks traités: ~{chunks_processed}")
    print(f"   • Chunks restants: ~{max(0, len(chunks) - chunks_processed)}")

    if n_checkpoints > 0:
        progress = min(100, (chunks_processed / len(chunks)) * 100)
        print(f"   • Progression: {progress:.1f}%")

    # Index FAISS
    faiss_path = config.vector_store_path / "index.faiss"
    if faiss_path.exists():
        print(f"\n🗃️  Index FAISS: ✅ Créé ({faiss_path})")
    else:
        print(f"\n🗃️  Index FAISS: ❌ Non créé")

    # Index BM25
    bm25_path = config.index_dir / "bm25_index.pkl"
    if bm25_path.exists():
        print(f"📚 Index BM25: ✅ Créé ({bm25_path})")
    else:
        print(f"📚 Index BM25: ❌ Non créé")

    # Index métadonnées
    metadata_path = config.index_dir / "metadata.db"
    if metadata_path.exists():
        print(f"📋 Index métadonnées: ✅ Créé ({metadata_path})")
    else:
        print(f"📋 Index métadonnées: ❌ Non créé")

    print()


def reset_checkpoints():
    """Supprime tous les checkpoints."""
    if CHECKPOINT_DIR.exists():
        import shutil
        shutil.rmtree(CHECKPOINT_DIR)
        print("🗑️  Checkpoints supprimés")


def main():
    parser = argparse.ArgumentParser(description="Indexation RAG avec batching et reprise")
    parser.add_argument("--reset", action="store_true", help="Repart de zéro")
    parser.add_argument("--status", action="store_true", help="Affiche l'état actuel")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help=f"Taille des batches (défaut: {BATCH_SIZE})")
    args = parser.parse_args()

    config = Config()

    if args.status:
        show_status(config)
        return

    if args.reset:
        reset_checkpoints()
        # Supprimer aussi l'index FAISS
        if config.vector_store_path.exists():
            import shutil
            shutil.rmtree(config.vector_store_path)
            print("🗑️  Index FAISS supprimé")
        print()

    batch_size = args.batch_size

    print("=" * 60)
    print("🚀 RAG Pipeline - Indexation avec BATCHING")
    print("=" * 60)
    print()
    print(f"📦 Batch size: {batch_size}")
    print(f"💾 Checkpoints: {CHECKPOINT_DIR}")
    print()

    # ========================================
    # Étape 1: Charger les chunks
    # ========================================
    print("=" * 40)
    print("📝 Étape 1/6: Chargement des chunks")
    print("=" * 40)

    chunker = ConversationChunker(config)

    # Vérifier si les chunks existent
    if config.chunks_cache_path.exists():
        print(f"📂 Chargement depuis {config.chunks_cache_path}...")
        chunks = chunker.load_chunks()
        print(f"✅ {len(chunks)} chunks chargés")
    else:
        print("⚠️  Pas de chunks en cache, génération en cours...")

        def progress_callback(current, total, filename, num_chunks):
            if current % 100 == 0 or current == total:
                print(f"   [{current}/{total}] {filename} → {num_chunks} chunks")

        chunks = chunker.chunk_all_conversations(progress_callback=progress_callback)
        chunker.save_chunks(chunks)
        print(f"✅ {len(chunks)} chunks créés et sauvegardés")

    print()

    # ========================================
    # Étape 2: Enrichissement LLM (Gold Standard RAG)
    # ========================================
    print("=" * 40)
    print("✨ Étape 2/6: Enrichissement sémantique (LLM)")
    print("=" * 40)
    
    from rag_pipeline.enricher import ChunkEnricher
    enricher = ChunkEnricher(config)
    
    # Vérifier combien de chunks ont besoin d'être enrichis
    to_enrich = [c for c in chunks if not c.narrative_summary or not c.hypothetical_questions]
    
    if not to_enrich:
        print("✅ Tous les chunks sont déjà enrichis.")
    else:
        print(f"🧠 Enrichissement de {len(to_enrich)} chunks via Ollama ({config.llm_model})...")
        print("   Cela améliore drastiquement la qualité de la recherche.")
        print(f"   (Sauvegarde automatique tous les 20 chunks)")
        
        try:
            start_time = time.time()
            
            def enrich_progress(current, total):
                if current % 5 == 0 or current == total:
                    elapsed = time.time() - start_time
                    speed = current / elapsed if elapsed > 0 else 0
                    remaining = (total - current) / speed if speed > 0 else 0
                    
                    # Formatter le temps restant
                    rem_str = f"{int(remaining // 60)}m {int(remaining % 60)}s"
                    
                    sys.stdout.write(f"\r   ✨ [{current}/{total}] chunks | Vitesse: {speed:.1f} ch/s | Reste: {rem_str}   ")
                    sys.stdout.flush()

            def save_progress():
                chunker.save_chunks(chunks)
                # On revient à la ligne après une sauvegarde pour garder une trace
                sys.stdout.write("\n")
            
            enricher.enrich_batch(
                to_enrich, 
                progress_callback=enrich_progress,
                save_callback=save_progress,
                save_interval=20
            )
            
            print("\n✅ Chunks enrichis et sauvegardés en cache.")

        except KeyboardInterrupt:
            print("\n\n⚠️ Interruption : Sauvegarde des chunks déjà enrichis...")
            chunker.save_chunks(chunks)
            print("✅ Sauvegarde effectuée. Relancez le script pour reprendre.")
            sys.exit(0)
        except Exception as e:
            print(f"\n\n⚠️ Erreur pendant l'enrichissement: {e}")
            print("   Tentative de sauvegarde du travail effectué...")
            chunker.save_chunks(chunks)
            print("   L'indexation continue avec les données disponibles.")

    print()

    # ========================================
    # Étape 3: Génération des embeddings par batch
    # ========================================
    print("=" * 40)
    print("🧠 Étape 3/6: Génération des embeddings (batched)")
    print("=" * 40)


    # Créer le dossier checkpoints
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    # Déterminer où reprendre (compter les embeddings réels, pas juste les checkpoints)
    existing_checkpoints = count_existing_checkpoints()
    start_idx = count_existing_embeddings() if existing_checkpoints > 0 else 0

    if start_idx >= len(chunks):
        print(f"✅ Tous les embeddings sont déjà générés ({existing_checkpoints} checkpoints)")
        embeddings = load_all_checkpoints()
    else:
        if existing_checkpoints > 0:
            print(f"🔄 Reprise depuis le checkpoint {existing_checkpoints}")
            print(f"   Embeddings existants: {start_idx}")
            print(f"   Chunks restants: {len(chunks) - start_idx}")

        print()

        # Charger le modèle d'embeddings
        embedding_model = EmbeddingModel(config)

        # Calculer le nombre de batches restants
        remaining_chunks = len(chunks) - start_idx
        n_batches = (remaining_chunks + batch_size - 1) // batch_size

        print(f"📊 {n_batches} batch(es) à traiter")
        print()

        total_start_time = time.time()

        for batch_num in range(n_batches):
            batch_start = start_idx + (batch_num * batch_size)
            batch_end = min(batch_start + batch_size, len(chunks))
            batch_chunks = chunks[batch_start:batch_end]

            checkpoint_idx = existing_checkpoints + batch_num
            checkpoint_path = get_checkpoint_path(checkpoint_idx)

            print(f"📦 Batch {batch_num + 1}/{n_batches} (chunks {batch_start}-{batch_end})")

            # Préparer les textes
            texts = [chunk.get_embedding_text() for chunk in batch_chunks]

            # Encoder
            batch_start_time = time.time()
            batch_embeddings = embedding_model.encode(texts, show_progress=True)
            batch_time = time.time() - batch_start_time

            # Sauvegarder le checkpoint
            np.save(checkpoint_path, batch_embeddings)

            print(f"   ✅ Sauvegardé: {checkpoint_path.name}")
            print(f"   ⏱️  Temps: {batch_time:.1f}s ({batch_time/len(batch_chunks):.2f}s/chunk)")
            print()

        total_time = time.time() - total_start_time
        print(f"✅ Génération terminée en {total_time:.1f}s")
        print()

        # Charger tous les embeddings
        print("📂 Chargement de tous les embeddings...")
        embeddings = load_all_checkpoints()

    print(f"\n📊 Shape finale: {embeddings.shape}")
    print(f"   • {embeddings.shape[0]} vecteurs")
    print(f"   • {embeddings.shape[1]} dimensions")
    print(f"   • {embeddings.nbytes / 1024 / 1024:.1f} MB")
    print()

    # Vérification de cohérence
    if len(embeddings) != len(chunks):
        print(f"⚠️  ATTENTION: {len(embeddings)} embeddings ≠ {len(chunks)} chunks")
        print("   Utilisez --reset pour recommencer proprement")
        sys.exit(1)

    # ========================================
    # Étape 3: Construction de l'index FAISS
    # ========================================
    print("=" * 40)
    print("🗃️  Étape 4/6: Construction de l'index FAISS")
    print("=" * 40)

    vector_store = VectorStore(config)
    vector_store.build_index(chunks, embeddings)
    vector_store.save()

    print()

    # ========================================
    # Étape 4: Construction des index avancés
    # ========================================
    print("=" * 40)
    print("📚 Étape 5/6: Index BM25 (recherche lexicale)")
    print("=" * 40)

    from rag_pipeline.bm25_index import BM25Index
    bm25_index = BM25Index(config)
    bm25_index.chunks = chunks
    bm25_index.build_index(chunks)
    bm25_index.save()

    print()

    # ========================================
    # Étape 5: Index métadonnées (pre-filtering)
    # ========================================
    print("=" * 40)
    print("📋 Étape 6/6: Index métadonnées (SQLite)")
    print("=" * 40)

    from rag_pipeline.metadata_store import MetadataStore
    metadata_store = MetadataStore(config)
    metadata_store.build_index(chunks)

    # Afficher quelques stats
    participants = metadata_store.get_all_participants()[:10]
    date_range = metadata_store.get_date_range()
    print(f"   • Période: {date_range[0][:10] if date_range[0] else 'N/A'} → {date_range[1][:10] if date_range[1] else 'N/A'}")
    print(f"   • Top participants: {', '.join(p[0] for p in participants[:5])}")

    metadata_store.close()
    print()

    # ========================================
    # Résumé final
    # ========================================
    print("=" * 60)
    print("✅ INDEXATION TERMINÉE - RAG AVANCÉ")
    print("=" * 60)
    print(f"📝 Chunks indexés: {len(chunks)}")
    print(f"🧠 Embeddings: {embeddings.shape}")
    print(f"🗃️  Index FAISS: {config.vector_store_path}")
    print(f"📚 Index BM25: {config.index_dir / 'bm25_index.pkl'}")
    print(f"📋 Index métadonnées: {config.index_dir / 'metadata.db'}")
    print()
    print("🎉 Vous pouvez maintenant lancer le chat avancé avec:")
    print("   python3 chat_instagram_advanced.py")
    print()
    print("   Ou le chat simple avec:")
    print("   python3 chat_instagram.py")
    print()


if __name__ == "__main__":
    main()
