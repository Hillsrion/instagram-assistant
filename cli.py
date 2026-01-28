#!/usr/bin/env python3
"""
Interface CLI pour converser avec vos conversations Instagram.
Utilise le RAG Pipeline avancé avec Ollama.
"""
import sys
import readline  # Pour l'historique des commandes
import argparse
from pathlib import Path

from rag_pipeline.config import Config
from rag_pipeline.advanced_retriever import create_advanced_retriever
from rag_pipeline.chat import ChatBot
from rag_pipeline.query_analyzer import QueryAnalyzer
from rag_pipeline.logger import initialize_logging


# Couleurs ANSI pour le terminal
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def print_header():
    """Affiche l'en-tête du programme."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}🤖 Instagram Assistant - Chat CLI{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}\n")
    print(f"{Colors.DIM}Posez des questions sur vos conversations Instagram.{Colors.RESET}")
    print(f"{Colors.DIM}Tapez 'exit', 'quit' ou Ctrl+D pour quitter.{Colors.RESET}")
    print(f"{Colors.DIM}Tapez 'help' pour voir les commandes disponibles.{Colors.RESET}\n")


def print_help():
    """Affiche l'aide."""
    print(f"\n{Colors.BOLD}Commandes disponibles:{Colors.RESET}")
    print(f"  {Colors.CYAN}help{Colors.RESET}              - Afficher cette aide")
    print(f"  {Colors.CYAN}exit/quit{Colors.RESET}         - Quitter le programme")
    print(f"  {Colors.CYAN}clear{Colors.RESET}             - Effacer l'historique de conversation")
    print(f"  {Colors.CYAN}stats{Colors.RESET}             - Afficher les statistiques du système")
    print(f"  {Colors.CYAN}filters on/off{Colors.RESET}    - Activer/désactiver les filtres avancés")
    print()
    print(f"{Colors.BOLD}Exemples de questions:{Colors.RESET}")
    print(f"  • Qu'ai-je discuté avec Marie en 2024 ?")
    print(f"  • Résume mes conversations de janvier")
    print(f"  • De quoi parlait ma dernière discussion ?")
    print()


def print_sources(results, max_sources=5):
    """Affiche les sources utilisées."""
    if not results:
        return

    print(f"\n{Colors.DIM}{'─'*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.YELLOW}📚 Sources ({len(results)} documents):{Colors.RESET}")

    for i, result in enumerate(results[:max_sources], 1):
        chunk = result.chunk
        expanded = f" {Colors.MAGENTA}[contexte adjacent]{Colors.RESET}" if result.is_expanded else ""

        print(f"\n{Colors.BOLD}[{i}]{Colors.RESET} {Colors.CYAN}{chunk.file_source}{Colors.RESET}{expanded}")
        print(f"    Participants: {', '.join(chunk.participants)}")
        print(f"    Période: {chunk.date_start[:10]} → {chunk.date_end[:10]}")
        print(f"    Score: {Colors.GREEN}{result.final_score:.2f}{Colors.RESET}")

        # Afficher un extrait du résumé narratif
        if chunk.narrative_summary:
            summary = chunk.narrative_summary[:150]
            if len(chunk.narrative_summary) > 150:
                summary += "..."
            print(f"    {Colors.DIM}{summary}{Colors.RESET}")

    if len(results) > max_sources:
        print(f"\n{Colors.DIM}... et {len(results) - max_sources} autres sources{Colors.RESET}")

    print(f"{Colors.DIM}{'─'*70}{Colors.RESET}\n")


def main_noninteractive(query):
    """Exécute une seule question et quitte (mode --prompt)."""
    try:
        config = Config()

        # Vérifier que l'index existe
        if not (config.vector_store_path / "index.faiss").exists():
            print(f"{Colors.RED}❌ Erreur: Index FAISS non trouvé.{Colors.RESET}")
            print(f"{Colors.YELLOW}Veuillez exécuter setup_rag_batch.py d'abord.{Colors.RESET}")
            sys.exit(1)

        # Charger les composants RAG
        print(f"{Colors.YELLOW}⏳ Chargement du système RAG...{Colors.RESET}")
        retriever, components = create_advanced_retriever(
            config,
            enable_reranking=True,
            enable_bm25=True,
            enable_metadata=True
        )

        # Créer le chatbot
        chatbot = ChatBot(retriever, config)
        query_analyzer = QueryAnalyzer(config)
        print(f"{Colors.GREEN}✅ Système chargé ({components['vector_store'].size} chunks){Colors.RESET}\n")

        # Traiter la question
        print(f"{Colors.BOLD}{Colors.BLUE}Vous:{Colors.RESET} {query}\n")
        print(f"{Colors.DIM}🔍 Analyse de la question...{Colors.RESET}", end='\r')

        analysis = query_analyzer.analyze(query, [])

        dyn_top_k = analysis.top_k
        dyn_reranking = analysis.use_reranking
        dyn_expand = analysis.expand_context
        search_query = analysis.rewritten_query

        print(f"{Colors.DIM}🔍 Recherche ({analysis.intent}, k={dyn_top_k})...{Colors.RESET}", end='\r')

        context = retriever.retrieve(
            query=search_query,
            top_k=dyn_top_k,
            date_start=analysis.date_start,
            date_end=analysis.date_end,
            use_reranking=dyn_reranking,
            expand_context=dyn_expand
        )

        if not context.has_results:
            print(f"{Colors.YELLOW}⚠️  Aucun document pertinent trouvé.{Colors.RESET}\n")
            sys.exit(0)

        # Afficher les sources
        print_sources(context.results)

        # Générer la réponse
        print(f"{Colors.BOLD}{Colors.GREEN}Assistant:{Colors.RESET} ", end='', flush=True)

        prompt = chatbot._build_prompt(query, context)

        # Streaming de la réponse
        response_text = ""
        for token in chatbot._chat_stream(query, prompt, context):
            print(token, end='', flush=True)
            response_text += token

        print("\n")

    except Exception as e:
        print(f"\n{Colors.RED}❌ Erreur: {e}{Colors.RESET}\n")
        sys.exit(1)


def print_stats(components):
    """Affiche les statistiques du système."""
    vector_store = components['vector_store']
    metadata_store = components.get('metadata_store')

    print(f"\n{Colors.BOLD}{Colors.CYAN}📊 Statistiques du système:{Colors.RESET}")
    print(f"  Chunks indexés: {Colors.GREEN}{vector_store.size}{Colors.RESET}")

    if metadata_store:
        # Requête pour obtenir le nombre de conversations
        cursor = metadata_store.conn.execute("SELECT COUNT(DISTINCT file_source) FROM chunks")
        conv_count = cursor.fetchone()[0]

        # Obtenir la plage de dates
        cursor = metadata_store.conn.execute(
            "SELECT MIN(date_start), MAX(date_end) FROM chunks"
        )
        date_range = cursor.fetchone()

        print(f"  Conversations: {Colors.GREEN}{conv_count}{Colors.RESET}")
        if date_range[0] and date_range[1]:
            print(f"  Période: {Colors.GREEN}{date_range[0][:10]} → {date_range[1][:10]}{Colors.RESET}")

    print()


def main():
    """Point d'entrée principal."""
    # Parser les arguments
    parser = argparse.ArgumentParser(
        description='Instagram Assistant - Chat CLI',
        add_help=False
    )
    parser.add_argument(
        '--prompt',
        type=str,
        help='Question à poser (mode non-interactif)'
    )
    parser.add_argument(
        '-h', '--help',
        action='store_true',
        help='Afficher l\'aide'
    )
    parser.add_argument(
        '--log-verbose',
        action='store_true',
        help='Activer les logs détaillés'
    )

    args = parser.parse_args()

    # Initialiser le logging selon le flag
    initialize_logging(args.log_verbose)

    if args.help:
        parser.print_help()
        print_help()
        sys.exit(0)

    if args.prompt:
        # Mode non-interactif: exécuter une seule question
        return main_noninteractive(args.prompt)

    print_header()

    # Initialisation
    print(f"{Colors.YELLOW}⏳ Chargement du système RAG...{Colors.RESET}")

    try:
        config = Config()

        # Vérifier que l'index existe
        if not (config.vector_store_path / "index.faiss").exists():
            print(f"\n{Colors.RED}❌ Erreur: Index FAISS non trouvé.{Colors.RESET}")
            print(f"{Colors.YELLOW}Veuillez exécuter setup_rag_batch.py d'abord.{Colors.RESET}\n")
            sys.exit(1)

        # Charger les composants RAG
        retriever, components = create_advanced_retriever(
            config,
            enable_reranking=True,
            enable_bm25=True,
            enable_metadata=True
        )

        # Créer le chatbot
        chatbot = ChatBot(retriever, config)
        query_analyzer = QueryAnalyzer(config)

        print(f"{Colors.GREEN}✅ Système chargé ({components['vector_store'].size} chunks){Colors.RESET}\n")

    except Exception as e:
        print(f"\n{Colors.RED}❌ Erreur lors du chargement: {e}{Colors.RESET}\n")
        sys.exit(1)

    # Options de recherche
    use_reranking = True
    use_hybrid = True
    expand_context = True

    # Boucle principale
    try:
        while True:
            try:
                # Demander la question
                query = input(f"{Colors.BOLD}{Colors.BLUE}Vous:{Colors.RESET} ").strip()

                if not query:
                    continue

                # Commandes spéciales
                if query.lower() in ['exit', 'quit']:
                    print(f"\n{Colors.CYAN}👋 Au revoir!{Colors.RESET}\n")
                    break

                elif query.lower() == 'help':
                    print_help()
                    continue

                elif query.lower() == 'clear':
                    chatbot.conversation_history.clear()
                    print(f"{Colors.GREEN}✅ Historique effacé{Colors.RESET}\n")
                    continue

                elif query.lower() == 'stats':
                    print_stats(components)
                    continue

                elif query.lower().startswith('filters'):
                    parts = query.lower().split()
                    if len(parts) == 2:
                        if parts[1] == 'on':
                            use_reranking = use_hybrid = expand_context = True
                            print(f"{Colors.GREEN}✅ Filtres avancés activés{Colors.RESET}\n")
                        elif parts[1] == 'off':
                            use_reranking = use_hybrid = expand_context = False
                            print(f"{Colors.YELLOW}⚠️  Filtres avancés désactivés{Colors.RESET}\n")
                    continue

                # Recherche
                print(f"\n{Colors.DIM}🔍 Analyse de la question...{Colors.RESET}", end='\r')
                analysis = query_analyzer.analyze(query, chatbot.conversation_history)
                
                dyn_top_k = analysis.top_k
                dyn_reranking = analysis.use_reranking
                dyn_expand = analysis.expand_context
                search_query = analysis.rewritten_query
                
                print(f"{Colors.DIM}🔍 Recherche ({analysis.intent}, k={dyn_top_k})...{Colors.RESET}", end='\r')

                context = retriever.retrieve(
                    query=search_query,
                    top_k=dyn_top_k,
                    date_start=analysis.date_start,
                    date_end=analysis.date_end,
                    use_reranking=dyn_reranking,
                    use_hybrid=use_hybrid,
                    expand_context=dyn_expand
                )

                if not context.has_results:
                    print(f"{Colors.YELLOW}⚠️  Aucun document pertinent trouvé.{Colors.RESET}\n")
                    continue

                # Afficher les sources
                print_sources(context.results)

                # Générer la réponse
                print(f"{Colors.BOLD}{Colors.GREEN}Assistant:{Colors.RESET} ", end='', flush=True)

                prompt = chatbot._build_prompt(query, context)

                # Streaming de la réponse
                response_text = ""
                for token in chatbot._chat_stream(query, prompt, context):
                    print(token, end='', flush=True)
                    response_text += token

                print("\n")

            except KeyboardInterrupt:
                print(f"\n\n{Colors.YELLOW}Interruption (Ctrl+C détecté){Colors.RESET}")
                print(f"{Colors.DIM}Tapez 'exit' pour quitter ou continuez à poser des questions.{Colors.RESET}\n")
                continue

            except Exception as e:
                print(f"\n{Colors.RED}❌ Erreur: {e}{Colors.RESET}\n")
                continue

    except EOFError:
        # Ctrl+D
        print(f"\n\n{Colors.CYAN}👋 Au revoir!{Colors.RESET}\n")

    except Exception as e:
        print(f"\n{Colors.RED}❌ Erreur fatale: {e}{Colors.RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
