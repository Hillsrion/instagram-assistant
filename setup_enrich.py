#!/usr/bin/env python3
"""
Étape 2: Enrichissement sémantique des chunks via LLM.

Ce script enrichit les chunks avec des résumés narratifs et des questions
hypothétiques pour améliorer la qualité de la recherche RAG.

Usage:
    python setup_enrich.py              # Enrichit les chunks non traités
    python setup_enrich.py --reset      # Ré-enrichit tous les chunks
    python setup_enrich.py --model qwen2.5:3b  # Override du modèle LLM
"""
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.enricher import ChunkEnricher
from rag_pipeline.cli_utils import print_header, format_duration


def run(config: Config, reset: bool = False, model: str = None, total_shards: int = 1, shard_index: int = 0) -> bool:
    """Point d'entrée appelable par l'orchestrateur.

    Args:
        config: Configuration du pipeline
        reset: Si True, ré-enrichit tous les chunks
        model: Override du modèle LLM
        total_shards: Nombre total de machines/processus
        shard_index: Index de ce processus (0 à total_shards-1)

    Returns:
        True si succès, False sinon
    """
    if model:
        config.llm_model = model
        print(f"Override modèle LLM: {config.llm_model}")

    print_header("Enrichissement sémantique (LLM)", step="2/8")
    if total_shards > 1:
        print(f"Mode distribué: Shard {shard_index + 1}/{total_shards}")

    # Charger les chunks
    chunker = ConversationChunker(config)
    if not config.chunks_cache_path.exists():
        print("Erreur: Pas de chunks trouvés. Exécutez d'abord setup_chunks.py")
        return False

    chunks = chunker.load_chunks()
    print(f"{len(chunks)} chunks chargés")

    # Déterminer quels chunks enrichir
    if reset:
        to_enrich_all = chunks
        print(f"Reset demandé: ré-enrichissement de tous les {len(chunks)} chunks")
        # Reset les champs d'enrichissement
        for c in to_enrich_all:
            c.narrative_summary = None
            c.hypothetical_questions = []
    else:
        to_enrich_all = [c for c in chunks if not c.narrative_summary or not c.hypothetical_questions]

    # Application du sharding
    if total_shards > 1:
        to_enrich = [c for i, c in enumerate(to_enrich_all) if i % total_shards == shard_index]
        print(f"Shard {shard_index}: Traitement de {len(to_enrich)} chunks sur les {len(to_enrich_all)} restants")
    else:
        to_enrich = to_enrich_all

    if not to_enrich:
        print("Tous les chunks assignés à ce shard sont déjà enrichis.")
        print()
        return True

    print(f"Enrichissement de {len(to_enrich)} chunks via Ollama ({config.llm_model})...")
    print("   Cela améliore drastiquement la qualité de la recherche.")
    print("   (Sauvegarde automatique tous les 20 chunks)")

    enricher = ChunkEnricher(config)

    try:
        start_time = time.time()

        def enrich_progress(current, total):
            if current % 5 == 0 or current == total:
                elapsed = time.time() - start_time
                speed = current / elapsed if elapsed > 0 else 0
                remaining = (total - current) / speed if speed > 0 else 0

                rem_str = format_duration(remaining)

                sys.stdout.write(f"\r   [{current}/{total}] chunks | Vitesse: {speed:.1f} ch/s | Reste: {rem_str}   ")
                sys.stdout.flush()

        def save_progress():
            # En mode shard, on sauvegarde quand même dans le fichier principal
            # car on a chargé tous les chunks en mémoire, on ne modifie que les nôtres.
            chunker.save_chunks(chunks)
            sys.stdout.write("\n")

        enricher.enrich_batch(
            to_enrich,
            progress_callback=enrich_progress,
            save_callback=save_progress,
            save_interval=20
        )

        chunker.save_chunks(chunks)
        print("\nChunks enrichis et sauvegardés en cache.")

    except KeyboardInterrupt:
        print("\n\nInterruption: Sauvegarde des chunks déjà enrichis...")
        chunker.save_chunks(chunks)
        print("Sauvegarde effectuée. Relancez le script pour reprendre.")
        return False

    except Exception as e:
        print(f"\n\nErreur pendant l'enrichissement: {e}")
        print("   Tentative de sauvegarde du travail effectué...")
        chunker.save_chunks(chunks)
        print("   Sauvegarde effectuée.")
        return False

    print()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Étape 2: Enrichissement sémantique des chunks via LLM"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Ré-enrichit tous les chunks")
    parser.add_argument("--model", type=str,
                        help="Override du modèle LLM (ex: qwen2.5:3b)")
    parser.add_argument("--total-shards", type=int, default=1,
                        help="Nombre total de machines participant")
    parser.add_argument("--shard-index", type=int, default=0,
                        help="Index de cette machine (0 à total-shards - 1)")

    args = parser.parse_args()
    config = Config()

    success = run(
        config,
        reset=args.reset,
        model=args.model,
        total_shards=args.total_shards,
        shard_index=args.shard_index
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
