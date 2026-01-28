#!/usr/bin/env python3
"""
Étapes 4-6: Construction des index (FAISS, BM25, Métadonnées SQLite).

Ce script construit les différents index nécessaires au RAG:
- Index FAISS pour la recherche vectorielle
- Index BM25 pour la recherche lexicale
- Index SQLite pour le filtrage par métadonnées

Usage:
    python setup_indexes.py              # Construit tous les index
    python setup_indexes.py --reset      # Reconstruit tous les index
    python setup_indexes.py --only faiss # Construit seulement FAISS
    python setup_indexes.py --only bm25  # Construit seulement BM25
    python setup_indexes.py --only metadata  # Construit seulement métadonnées
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.vector_store import VectorStore
from rag_pipeline.bm25_index import BM25Index
from rag_pipeline.metadata_store import MetadataStore
from rag_pipeline.cli_utils import print_header, load_all_checkpoints, CHECKPOINT_DIR


def build_faiss_index(config: Config, chunks: list, embeddings) -> bool:
    """Construit l'index FAISS."""
    print_header("Construction de l'index FAISS", step="4/8")

    if embeddings is None:
        print("Erreur: Pas d'embeddings disponibles.")
        return False

    vector_store = VectorStore(config)
    vector_store.build_index(chunks, embeddings)
    vector_store.save()
    print("Index FAISS construit et sauvegardé")
    print()
    return True


def build_bm25_index(config: Config, chunks: list) -> bool:
    """Construit l'index BM25."""
    print_header("Index BM25 (recherche lexicale)", step="5/8")

    bm25_index = BM25Index(config)
    bm25_index.chunks = chunks
    bm25_index.build_index(chunks)
    bm25_index.save()
    print("Index BM25 construit et sauvegardé")
    print()
    return True


def build_metadata_index(config: Config, chunks: list) -> bool:
    """Construit l'index métadonnées SQLite."""
    print_header("Index métadonnées (SQLite)", step="6/8")

    metadata_store = MetadataStore(config)
    metadata_store.build_index(chunks)

    # Afficher quelques stats
    participants = metadata_store.get_all_participants()[:10]
    date_range = metadata_store.get_date_range()
    print(f"   - Période: {date_range[0][:10] if date_range[0] else 'N/A'} -> {date_range[1][:10] if date_range[1] else 'N/A'}")
    print(f"   - Top participants: {', '.join(p[0] for p in participants[:5])}")

    metadata_store.close()
    print("Index métadonnées construit et sauvegardé")
    print()
    return True


def run(config: Config, reset: bool = False, only: str = None) -> bool:
    """Point d'entrée appelable par l'orchestrateur.

    Args:
        config: Configuration du pipeline
        reset: Si True, reconstruit tous les index
        only: Construit seulement un index spécifique ('faiss', 'bm25', 'metadata')

    Returns:
        True si succès, False sinon
    """
    # Charger les chunks
    chunker = ConversationChunker(config)
    if not config.chunks_cache_path.exists():
        print("Erreur: Pas de chunks trouvés. Exécutez d'abord setup_chunks.py")
        return False

    chunks = chunker.load_chunks()
    print(f"{len(chunks)} chunks chargés")

    # Charger les embeddings si nécessaire
    embeddings = None
    if only is None or only == 'faiss':
        embeddings = load_all_checkpoints(CHECKPOINT_DIR, verbose=False)
        if embeddings is None:
            print("Erreur: Pas d'embeddings trouvés. Exécutez d'abord setup_embeddings.py")
            if only == 'faiss':
                return False

    # Reset si demandé
    if reset:
        import shutil
        if only is None or only == 'faiss':
            if config.vector_store_path.exists():
                shutil.rmtree(config.vector_store_path)
                print("Index FAISS supprimé")
        if only is None or only == 'bm25':
            bm25_path = config.index_dir / "bm25_index.pkl"
            if bm25_path.exists():
                bm25_path.unlink()
                print("Index BM25 supprimé")
        if only is None or only == 'metadata':
            metadata_path = config.index_dir / "metadata.db"
            if metadata_path.exists():
                metadata_path.unlink()
                print("Index métadonnées supprimé")
        print()

    success = True

    # Construire les index demandés
    if only is None or only == 'faiss':
        if not build_faiss_index(config, chunks, embeddings):
            success = False

    if only is None or only == 'bm25':
        if not build_bm25_index(config, chunks):
            success = False

    if only is None or only == 'metadata':
        if not build_metadata_index(config, chunks):
            success = False

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Étapes 4-6: Construction des index (FAISS, BM25, Métadonnées)"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Reconstruit tous les index")
    parser.add_argument("--only", choices=['faiss', 'bm25', 'metadata'],
                        help="Construit seulement un index spécifique")

    args = parser.parse_args()
    config = Config()

    success = run(
        config,
        reset=args.reset,
        only=args.only
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
