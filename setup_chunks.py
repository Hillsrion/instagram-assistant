#!/usr/bin/env python3
"""
Étape 1: Chargement et génération des chunks.

Ce script charge les conversations Instagram et les découpe en chunks
pour le traitement RAG.

Usage:
    python setup_chunks.py              # Charge/génère les chunks
    python setup_chunks.py --reset      # Régénère les chunks
    python setup_chunks.py --limit 10   # Limite à 10 conversations
    python setup_chunks.py --import-test  # Importe les conversations de test
"""
import sys
import shutil
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.cli_utils import print_header


def run(config: Config, reset: bool = False, limit: int = None, import_test: bool = False) -> bool:
    """Point d'entrée appelable par l'orchestrateur.

    Args:
        config: Configuration du pipeline
        reset: Si True, régénère les chunks même s'ils existent
        limit: Limite le nombre de conversations à traiter
        import_test: Importe les conversations de test

    Returns:
        True si succès, False sinon
    """
    # Import des conversations de test si demandé
    if import_test:
        test_dir = Path("test_conversations")
        target_dir = config.conversations_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        print_header("Importation des conversations de test")

        if test_dir.exists():
            count = 0
            for f in test_dir.glob("*.txt"):
                shutil.copy2(f, target_dir)
                print(f"   Copié: {f.name}")
                count += 1
            print(f"{count} conversations importées dans {target_dir}")
        else:
            print(f"Dossier de test introuvable: {test_dir}")
        print()

    print_header("Chargement des chunks", step="1/8")

    chunker = ConversationChunker(config)

    # Vérifier si les chunks existent
    if config.chunks_cache_path.exists() and not reset:
        print(f"Chargement depuis {config.chunks_cache_path}...")
        chunks = chunker.load_chunks()
        print(f"{len(chunks)} chunks chargés")
    else:
        if reset and config.chunks_cache_path.exists():
            print("Reset demandé: régénération des chunks...")
        else:
            print("Pas de chunks en cache, génération en cours...")

        def progress_callback(current, total, filename, num_chunks):
            if current % 100 == 0 or current == total:
                print(f"   [{current}/{total}] {filename} -> {num_chunks} chunks")

        chunks = chunker.chunk_all_conversations(
            progress_callback=progress_callback,
            limit=limit
        )
        chunker.save_chunks(chunks)
        print(f"{len(chunks)} chunks créés et sauvegardés")

    print()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Étape 1: Chargement et génération des chunks"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Régénère les chunks même s'ils existent")
    parser.add_argument("--limit", type=int,
                        help="Limite le nombre de conversations à traiter")
    parser.add_argument("--import-test", action="store_true",
                        help="Importe les conversations de test depuis test_conversations/")

    args = parser.parse_args()
    config = Config()

    success = run(
        config,
        reset=args.reset,
        limit=args.limit,
        import_test=args.import_test
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
