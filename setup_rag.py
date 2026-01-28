#!/usr/bin/env python3
"""
Orchestrateur du pipeline RAG - Point d'entrée principal.

Ce script orchestre l'exécution de toutes les étapes du pipeline RAG:
1. Chargement/génération des chunks (setup_chunks.py)
2. Enrichissement LLM (setup_enrich.py)
3. Génération des embeddings (setup_embeddings.py)
4-6. Index FAISS + BM25 + Métadonnées (setup_indexes.py)
7-8. Résumés hiérarchiques + leur index (setup_summaries.py)

Usage:
    python setup_rag.py                  # Exécute tout le pipeline
    python setup_rag.py --status         # Affiche l'état de tous les composants
    python setup_rag.py --reset          # Reset complet et recommence
    python setup_rag.py --only chunks    # Exécute une seule étape
    python setup_rag.py --skip-enrich    # Saute l'enrichissement
    python setup_rag.py --limit 10       # Limite à 10 conversations
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.logger import initialize_logging
from rag_pipeline.cli_utils import (
    print_header,
    CHECKPOINT_DIR,
    DEFAULT_BATCH_SIZE,
    count_existing_checkpoints,
    load_all_checkpoints,
    reset_checkpoints,
)

# Import des sous-scripts
import setup_chunks
import setup_enrich
import setup_embeddings
import setup_indexes
import setup_summaries


def show_status(config: Config):
    """Affiche l'état actuel de l'indexation."""
    print("=" * 60)
    print("STATUS - RAG Pipeline")
    print("=" * 60)

    # Chunks
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks() if config.chunks_cache_path.exists() else []
    print(f"\n[Chunks] {len(chunks)} (dans {config.chunks_cache_path})")

    # Enrichissement
    if chunks:
        enriched = sum(1 for c in chunks if c.narrative_summary and c.hypothetical_questions)
        print(f"[Enrichissement] {enriched}/{len(chunks)} chunks enrichis")

    # Checkpoints
    n_checkpoints = count_existing_checkpoints(CHECKPOINT_DIR)
    chunks_processed = n_checkpoints * DEFAULT_BATCH_SIZE
    print(f"\n[Embeddings]")
    print(f"   - Checkpoints: {n_checkpoints}")
    print(f"   - Chunks traités: ~{chunks_processed}")
    if chunks:
        print(f"   - Chunks restants: ~{max(0, len(chunks) - chunks_processed)}")
        if n_checkpoints > 0:
            progress = min(100, (chunks_processed / len(chunks)) * 100)
            print(f"   - Progression: {progress:.1f}%")

    # Index FAISS
    faiss_path = config.vector_store_path / "index.faiss"
    if faiss_path.exists():
        print(f"\n[Index FAISS] Créé ({faiss_path})")
    else:
        print(f"\n[Index FAISS] Non créé")

    # Index BM25
    bm25_path = config.index_dir / "bm25_index.pkl"
    if bm25_path.exists():
        print(f"[Index BM25] Créé ({bm25_path})")
    else:
        print(f"[Index BM25] Non créé")

    # Index métadonnées
    metadata_path = config.index_dir / "metadata.db"
    if metadata_path.exists():
        print(f"[Index métadonnées] Créé ({metadata_path})")
    else:
        print(f"[Index métadonnées] Non créé")

    # Résumés
    conv_summaries_path = config.index_dir / "conversation_summaries.json"
    period_summaries_path = config.index_dir / "period_summaries.json"
    summary_index_path = config.index_dir / "summary_index"

    if conv_summaries_path.exists():
        import json
        with open(conv_summaries_path, 'r', encoding='utf-8') as f:
            conv_data = json.load(f)
        print(f"\n[Résumés conversations] {len(conv_data)} résumés")
    else:
        print(f"\n[Résumés conversations] Non générés")

    if period_summaries_path.exists():
        import json
        with open(period_summaries_path, 'r', encoding='utf-8') as f:
            period_data = json.load(f)
        print(f"[Résumés périodes] {len(period_data)} résumés")
    else:
        print(f"[Résumés périodes] Non générés")

    if (summary_index_path / "conversation_index.faiss").exists():
        print(f"[Index résumés] Créé ({summary_index_path})")
    else:
        print(f"[Index résumés] Non créé")

    print()


def full_reset(config: Config):
    """Reset complet de tous les composants."""
    import shutil

    print("Reset complet du pipeline RAG...")

    # Checkpoints
    reset_checkpoints(CHECKPOINT_DIR)

    # Index FAISS
    if config.vector_store_path.exists():
        shutil.rmtree(config.vector_store_path)
        print("Index FAISS supprimé")

    # BM25
    bm25_path = config.index_dir / "bm25_index.pkl"
    if bm25_path.exists():
        bm25_path.unlink()
        print("Index BM25 supprimé")

    # Métadonnées
    metadata_path = config.index_dir / "metadata.db"
    if metadata_path.exists():
        metadata_path.unlink()
        print("Index métadonnées supprimé")

    # Résumés
    conv_summaries_path = config.index_dir / "conversation_summaries.json"
    period_summaries_path = config.index_dir / "period_summaries.json"
    summary_index_path = config.index_dir / "summary_index"

    if conv_summaries_path.exists():
        conv_summaries_path.unlink()
        print("Résumés de conversation supprimés")
    if period_summaries_path.exists():
        period_summaries_path.unlink()
        print("Résumés de période supprimés")
    if summary_index_path.exists():
        shutil.rmtree(summary_index_path)
        print("Index des résumés supprimé")

    # Chunks (optionnel - on les garde par défaut)
    # if config.chunks_cache_path.exists():
    #     config.chunks_cache_path.unlink()
    #     print("Cache des chunks supprimé")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Orchestrateur du pipeline RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
    python setup_rag.py                  # Exécute tout le pipeline
    python setup_rag.py --status         # Affiche l'état
    python setup_rag.py --reset          # Reset complet
    python setup_rag.py --only chunks    # Seulement les chunks
    python setup_rag.py --skip-enrich --skip-summary  # Sans enrichissement ni résumés
        """
    )

    # Options générales
    parser.add_argument("--status", action="store_true",
                        help="Affiche l'état de tous les composants")
    parser.add_argument("--reset", action="store_true",
                        help="Reset complet et recommence")

    # Exécution sélective
    parser.add_argument("--only", choices=['chunks', 'enrich', 'embed', 'indexes', 'summaries'],
                        help="Exécute une seule étape")

    # Options pour sauter des étapes
    parser.add_argument("--skip-enrich", action="store_true",
                        help="Saute l'enrichissement LLM")
    parser.add_argument("--skip-embed", action="store_true",
                        help="Saute la génération des embeddings")
    parser.add_argument("--skip-indexes", action="store_true",
                        help="Saute la création des index")
    parser.add_argument("--skip-summary", action="store_true",
                        help="Saute les résumés hiérarchiques")

    # Options passées aux sous-scripts
    parser.add_argument("--limit", type=int,
                        help="Limite le nombre de conversations")
    parser.add_argument("--model", type=str,
                        help="Override du modèle LLM (ex: qwen2.5:3b)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Taille des batches d'embeddings (défaut: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--import-test", action="store_true",
                        help="Importe les conversations de test")
    parser.add_argument("--log-verbose", action="store_true",
                        help="Activer les logs détaillés")

    args = parser.parse_args()

    # Initialiser le logging selon le flag
    initialize_logging(args.log_verbose)

    config = Config()

    if args.model:
        config.llm_model = args.model
        print(f"Override modèle LLM: {config.llm_model}")

    # Mode status
    if args.status:
        show_status(config)
        return

    # Mode reset
    if args.reset:
        full_reset(config)

    # Afficher la configuration
    print("=" * 60)
    print("RAG Pipeline - Indexation")
    print("=" * 60)
    print()
    if args.limit:
        print(f"Limite activée: {args.limit} conversations max")
    print(f"Batch size: {args.batch_size}")
    print(f"Checkpoints: {CHECKPOINT_DIR}")
    print()

    # Exécution sélective d'une seule étape
    if args.only:
        if args.only == 'chunks':
            setup_chunks.run(config, reset=args.reset, limit=args.limit, import_test=args.import_test)
        elif args.only == 'enrich':
            setup_enrich.run(config, reset=args.reset, model=args.model)
        elif args.only == 'embed':
            setup_embeddings.run(config, reset=args.reset, batch_size=args.batch_size)
        elif args.only == 'indexes':
            setup_indexes.run(config, reset=args.reset)
        elif args.only == 'summaries':
            setup_summaries.run(config, reset=args.reset, model=args.model)
        return

    # Exécution complète du pipeline
    # Étape 1: Chunks
    if not setup_chunks.run(config, reset=args.reset, limit=args.limit, import_test=args.import_test):
        print("Erreur à l'étape 1 (chunks)")
        sys.exit(1)

    # Étape 2: Enrichissement
    if not args.skip_enrich:
        if not setup_enrich.run(config, reset=args.reset, model=args.model):
            print("Erreur à l'étape 2 (enrichissement)")
            # Continue quand même car l'enrichissement n'est pas critique
    else:
        print("Étape 2/8: Enrichissement sauté (--skip-enrich)")
        print()

    # Étape 3: Embeddings
    embeddings = None
    if not args.skip_embed:
        embeddings = setup_embeddings.run(config, reset=args.reset, batch_size=args.batch_size)
        if embeddings is None:
            print("Erreur à l'étape 3 (embeddings)")
            sys.exit(1)
    else:
        print("Étape 3/8: Embeddings sauté (--skip-embed)")
        embeddings = load_all_checkpoints(CHECKPOINT_DIR, verbose=False)
        print()

    # Étapes 4-6: Index
    if not args.skip_indexes:
        if not setup_indexes.run(config, reset=args.reset):
            print("Erreur aux étapes 4-6 (indexes)")
            sys.exit(1)
    else:
        print("Étapes 4-6/8: Indexation sautée (--skip-indexes)")
        print()

    # Étapes 7-8: Résumés
    if not args.skip_summary:
        if not setup_summaries.run(config, reset=args.reset, model=args.model):
            print("Erreur aux étapes 7-8 (summaries)")
            # Continue quand même
    else:
        print("Étapes 7-8/8: Résumés sautés (--skip-summary)")
        print()

    # Résumé final
    print("=" * 60)
    print("INDEXATION TERMINÉE - RAG AVANCÉ")
    print("=" * 60)

    # Recharger les chunks pour le résumé
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks() if config.chunks_cache_path.exists() else []

    print(f"Chunks indexés: {len(chunks)}")
    if embeddings is not None:
        print(f"Embeddings: {embeddings.shape}")
    else:
        print(f"Embeddings: (Non chargés)")
    print(f"Index FAISS: {config.vector_store_path}")
    print(f"Index BM25: {config.index_dir / 'bm25_index.pkl'}")
    print(f"Index métadonnées: {config.index_dir / 'metadata.db'}")
    print(f"Index résumés: {config.index_dir / 'summary_index'}")
    print()
    print("Vous pouvez maintenant lancer le chat avancé avec:")
    print("   python chat_instagram_advanced.py")
    print()
    print("   Ou le chat simple avec:")
    print("   python chat_instagram.py")
    print()


if __name__ == "__main__":
    main()
