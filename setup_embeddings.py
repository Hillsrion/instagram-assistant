#!/usr/bin/env python3
"""
Étape 3: Génération des embeddings avec batching et checkpoints.

Ce script génère les embeddings pour tous les chunks avec sauvegarde
incrémentale par checkpoints pour permettre la reprise.

Usage:
    python setup_embeddings.py              # Génère/reprend les embeddings
    python setup_embeddings.py --reset      # Supprime les checkpoints et recommence
    python setup_embeddings.py --batch-size 100  # Taille des batches
"""
import sys
import time
import argparse
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.embeddings import EmbeddingModel
from rag_pipeline.cli_utils import (
    print_header,
    CHECKPOINT_DIR,
    DEFAULT_BATCH_SIZE,
    get_checkpoint_path,
    count_existing_checkpoints,
    count_existing_embeddings,
    load_all_checkpoints,
    reset_checkpoints,
)


def run(config: Config, reset: bool = False, batch_size: int = DEFAULT_BATCH_SIZE) -> np.ndarray:
    """Point d'entrée appelable par l'orchestrateur.

    Args:
        config: Configuration du pipeline
        reset: Si True, supprime les checkpoints et recommence
        batch_size: Taille des batches

    Returns:
        Array numpy des embeddings, ou None en cas d'erreur
    """
    print_header("Génération des embeddings (batched)", step="3/8")

    # Charger les chunks
    chunker = ConversationChunker(config)
    if not config.chunks_cache_path.exists():
        print("Erreur: Pas de chunks trouvés. Exécutez d'abord setup_chunks.py")
        return None

    chunks = chunker.load_chunks()
    print(f"{len(chunks)} chunks chargés")

    # Reset si demandé
    if reset:
        reset_checkpoints(CHECKPOINT_DIR)

    # Créer le dossier checkpoints
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    # Déterminer où reprendre
    existing_checkpoints = count_existing_checkpoints(CHECKPOINT_DIR)
    start_idx = count_existing_embeddings(CHECKPOINT_DIR) if existing_checkpoints > 0 else 0

    if start_idx >= len(chunks):
        print(f"Tous les embeddings sont déjà générés ({existing_checkpoints} checkpoints)")
        embeddings = load_all_checkpoints(CHECKPOINT_DIR)
    else:
        if existing_checkpoints > 0:
            print(f"Reprise depuis le checkpoint {existing_checkpoints}")
            print(f"   Embeddings existants: {start_idx}")
            print(f"   Chunks restants: {len(chunks) - start_idx}")

        print()

        # Charger le modèle d'embeddings
        embedding_model = EmbeddingModel(config)

        # Calculer le nombre de batches restants
        remaining_chunks = len(chunks) - start_idx
        n_batches = (remaining_chunks + batch_size - 1) // batch_size

        print(f"{n_batches} batch(es) à traiter")
        print()

        total_start_time = time.time()

        for batch_num in range(n_batches):
            batch_start = start_idx + (batch_num * batch_size)
            batch_end = min(batch_start + batch_size, len(chunks))
            batch_chunks = chunks[batch_start:batch_end]

            checkpoint_idx = existing_checkpoints + batch_num
            checkpoint_path = get_checkpoint_path(checkpoint_idx, CHECKPOINT_DIR)

            print(f"Batch {batch_num + 1}/{n_batches} (chunks {batch_start}-{batch_end})")

            # Préparer les textes
            texts = [chunk.get_embedding_text() for chunk in batch_chunks]

            # Encoder
            batch_start_time = time.time()
            batch_embeddings = embedding_model.encode(texts, show_progress=True)
            batch_time = time.time() - batch_start_time

            # Sauvegarder le checkpoint
            np.save(checkpoint_path, batch_embeddings)

            print(f"   Sauvegardé: {checkpoint_path.name}")
            print(f"   Temps: {batch_time:.1f}s ({batch_time/len(batch_chunks):.2f}s/chunk)")
            print()

        total_time = time.time() - total_start_time
        print(f"Génération terminée en {total_time:.1f}s")
        print()

        # Charger tous les embeddings
        print("Chargement de tous les embeddings...")
        embeddings = load_all_checkpoints(CHECKPOINT_DIR)

    print(f"\nShape finale: {embeddings.shape}")
    print(f"   - {embeddings.shape[0]} vecteurs")
    print(f"   - {embeddings.shape[1]} dimensions")
    print(f"   - {embeddings.nbytes / 1024 / 1024:.1f} MB")

    # Vérification de cohérence
    if len(embeddings) != len(chunks):
        print(f"ATTENTION: {len(embeddings)} embeddings != {len(chunks)} chunks")
        print("   Utilisez --reset pour recommencer proprement")
        return None

    print()
    return embeddings


def main():
    parser = argparse.ArgumentParser(
        description="Étape 3: Génération des embeddings avec batching et checkpoints"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Supprime les checkpoints et recommence")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Taille des batches (défaut: {DEFAULT_BATCH_SIZE})")

    args = parser.parse_args()
    config = Config()

    embeddings = run(
        config,
        reset=args.reset,
        batch_size=args.batch_size
    )

    sys.exit(0 if embeddings is not None else 1)


if __name__ == "__main__":
    main()
