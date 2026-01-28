#!/usr/bin/env python3
"""
Étapes 7-8: Génération des résumés hiérarchiques et leur index FAISS.

Ce script génère les résumés de conversations et de périodes via LLM,
puis construit un index FAISS dédié pour la recherche dans ces résumés.

Usage:
    python setup_summaries.py              # Génère les résumés et leur index
    python setup_summaries.py --reset      # Régénère tous les résumés
    python setup_summaries.py --model qwen2.5:3b  # Override du modèle LLM
"""
import sys
import time
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker
from rag_pipeline.embeddings import EmbeddingModel
from rag_pipeline.summary_generator import SummaryGenerator
from rag_pipeline.summary_store import SummaryStore
from rag_pipeline.summary_models import ConversationSummary, PeriodSummary
from rag_pipeline.cli_utils import print_header, format_duration


def run(config: Config, reset: bool = False, model: str = None) -> bool:
    """Point d'entrée appelable par l'orchestrateur.

    Args:
        config: Configuration du pipeline
        reset: Si True, régénère tous les résumés
        model: Override du modèle LLM

    Returns:
        True si succès, False sinon
    """
    if model:
        config.llm_model = model
        print(f"Override modèle LLM: {config.llm_model}")

    # Charger les chunks
    chunker = ConversationChunker(config)
    if not config.chunks_cache_path.exists():
        print("Erreur: Pas de chunks trouvés. Exécutez d'abord setup_chunks.py")
        return False

    chunks = chunker.load_chunks()
    print(f"{len(chunks)} chunks chargés")

    # Chemins des fichiers de résumés
    conv_summaries_path = config.index_dir / "conversation_summaries.json"
    period_summaries_path = config.index_dir / "period_summaries.json"
    summary_index_path = config.index_dir / "summary_index"

    # Reset si demandé
    if reset:
        import shutil
        if conv_summaries_path.exists():
            conv_summaries_path.unlink()
            print("Résumés de conversation supprimés")
        if period_summaries_path.exists():
            period_summaries_path.unlink()
            print("Résumés de période supprimés")
        if summary_index_path.exists():
            shutil.rmtree(summary_index_path)
            print("Index des résumés supprimé")
        print()

    # ========================================
    # Étape 7: Génération des résumés
    # ========================================
    print_header("Génération des résumés hiérarchiques (LLM)", step="7/8")

    conversation_summaries = []
    period_summaries = []

    if conv_summaries_path.exists() and period_summaries_path.exists() and not reset:
        print("Résumés hiérarchiques déjà générés.")
        with open(conv_summaries_path, 'r', encoding='utf-8') as f:
            conv_data = json.load(f)
        with open(period_summaries_path, 'r', encoding='utf-8') as f:
            period_data = json.load(f)
        print(f"   - {len(conv_data)} résumés de conversation")
        print(f"   - {len(period_data)} résumés de période")

        conversation_summaries = [ConversationSummary.from_dict(d) for d in conv_data]
        period_summaries = [PeriodSummary.from_dict(d) for d in period_data]
    else:
        print(f"Génération via Ollama ({config.llm_model})...")
        print("   Cette étape peut prendre du temps selon le nombre de conversations.")

        summary_generator = SummaryGenerator(config)

        try:
            summary_start_time = time.time()

            def summary_progress(current, total, desc=""):
                elapsed = time.time() - summary_start_time
                speed = current / elapsed if elapsed > 0 else 0
                remaining = (total - current) / speed if speed > 0 else 0
                rem_str = format_duration(remaining)
                sys.stdout.write(f"\r   [{current}/{total}] {desc[:40]:<40} | Reste: {rem_str}   ")
                sys.stdout.flush()

            def save_summaries(conv_sums, period_sums):
                with open(conv_summaries_path, 'w', encoding='utf-8') as f:
                    json.dump([s.to_dict() for s in conv_sums], f, ensure_ascii=False, indent=2)
                with open(period_summaries_path, 'w', encoding='utf-8') as f:
                    json.dump([s.to_dict() for s in period_sums], f, ensure_ascii=False, indent=2)

            conversation_summaries, period_summaries = summary_generator.generate_all_summaries(
                chunks,
                progress_callback=summary_progress,
                save_callback=save_summaries
            )

            print(f"\nRésumés générés: {len(conversation_summaries)} conversations, {len(period_summaries)} périodes")

        except KeyboardInterrupt:
            print("\n\nInterruption: les résumés partiels ont été sauvegardés.")
            print("   Relancez le script pour reprendre.")
            return False

        except Exception as e:
            print(f"\n\nErreur pendant la génération des résumés: {e}")
            return False

    print()

    # ========================================
    # Étape 8: Index FAISS des résumés
    # ========================================
    print_header("Index FAISS pour les résumés", step="8/8")

    conv_index_exists = (summary_index_path / "conversation_index.faiss").exists()
    period_index_exists = (summary_index_path / "period_index.faiss").exists()

    if conv_index_exists and period_index_exists and not reset:
        print("Index des résumés déjà construit.")
    else:
        if conversation_summaries or period_summaries:
            embedding_model = EmbeddingModel(config)
            summary_store = SummaryStore(config, embedding_model)
            summary_store.build_indexes(conversation_summaries, period_summaries)
            summary_store.save()
            print("Index des résumés construit et sauvegardé.")
        else:
            print("Aucun résumé à indexer.")

    print()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Étapes 7-8: Génération des résumés hiérarchiques et leur index"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Régénère tous les résumés")
    parser.add_argument("--model", type=str,
                        help="Override du modèle LLM (ex: qwen2.5:3b)")

    args = parser.parse_args()
    config = Config()

    success = run(
        config,
        reset=args.reset,
        model=args.model
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
