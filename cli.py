#!/usr/bin/env python3
"""
CLI interface to chat with your Instagram conversations.
Uses advanced RAG Pipeline with Ollama.
"""
import sys
import readline  # For command history
import argparse
from pathlib import Path

from rag_pipeline.config import Config
from rag_pipeline.advanced_retriever import create_advanced_retriever
from rag_pipeline.chat import ChatBot
from rag_pipeline.query_analyzer import QueryAnalyzer
from rag_pipeline.logger import initialize_logging


# ANSI colors for terminal
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
    """Displays program header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}🤖 Instagram Assistant - Chat CLI{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}\n")
    print(f"{Colors.DIM}Ask questions about your Instagram conversations.{Colors.RESET}")
    print(f"{Colors.DIM}Type 'exit', 'quit' or Ctrl+D to quit.{Colors.RESET}")
    print(f"{Colors.DIM}Type 'help' to see available commands.{Colors.RESET}\n")


def print_help():
    """Displays help."""
    print(f"\n{Colors.BOLD}Available commands:{Colors.RESET}")
    print(f"  {Colors.CYAN}help{Colors.RESET}              - Show this help")
    print(f"  {Colors.CYAN}exit/quit{Colors.RESET}         - Quit the program")
    print(f"  {Colors.CYAN}clear{Colors.RESET}             - Clear conversation history")
    print(f"  {Colors.CYAN}stats{Colors.RESET}             - Show system statistics")
    print(f"  {Colors.CYAN}filters on/off{Colors.RESET}    - Enable/disable advanced filters")
    print()
    print(f"{Colors.BOLD}Example questions:{Colors.RESET}")
    print(f"  • What did I discuss with Marie in 2024?")
    print(f"  • Summarize my January conversations")
    print(f"  • What was my last discussion about?")
    print()


def print_sources(results, max_sources=5):
    """Displays used sources."""
    if not results:
        return

    print(f"\n{Colors.DIM}{'─'*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.YELLOW}📚 Sources ({len(results)} documents):{Colors.RESET}")

    for i, result in enumerate(results[:max_sources], 1):
        chunk = result.chunk
        expanded = f" {Colors.MAGENTA}[adjacent context]{Colors.RESET}" if result.is_expanded else ""

        print(f"\n{Colors.BOLD}[{i}]{Colors.RESET} {Colors.CYAN}{chunk.file_source}{Colors.RESET}{expanded}")
        print(f"    Participants: {', '.join(chunk.participants)}")
        print(f"    Period: {chunk.date_start[:10]} → {chunk.date_end[:10]}")
        print(f"    Score: {Colors.GREEN}{result.final_score:.2f}{Colors.RESET}")

        # Show a snippet of narrative summary
        if chunk.narrative_summary:
            summary = chunk.narrative_summary[:150]
            if len(chunk.narrative_summary) > 150:
                summary += "..."
            print(f"    {Colors.DIM}{summary}{Colors.RESET}")

    if len(results) > max_sources:
        print(f"\n{Colors.DIM}... and {len(results) - max_sources} other sources{Colors.RESET}")

    print(f"{Colors.DIM}{'─'*70}{Colors.RESET}\n")


def main_noninteractive(query):
    """Executes a single question and exits (prompt mode)."""
    try:
        config = Config()

        # Check if index exists
        if not (config.vector_store_path / "index.faiss").exists():
            print(f"{Colors.RED}❌ Error: FAISS index not found.{Colors.RESET}")
            print(f"{Colors.YELLOW}Please run setup_rag_batch.py first.{Colors.RESET}")
            sys.exit(1)

        # Load RAG components
        print(f"{Colors.YELLOW}⏳ Loading RAG system...{Colors.RESET}")
        retriever, components = create_advanced_retriever(
            config,
            enable_reranking=True,
            enable_bm25=True,
            enable_metadata=True
        )

        # Create chatbot
        chatbot = ChatBot(retriever, config)
        query_analyzer = QueryAnalyzer(config)
        print(f"{Colors.GREEN}✅ System loaded ({components['vector_store'].size} chunks){Colors.RESET}\n")

        # Process question
        print(f"{Colors.BOLD}{Colors.BLUE}You:{Colors.RESET} {query}\n")
        print(f"{Colors.DIM}🔍 Analyzing question...{Colors.RESET}", end='\r')

        analysis = query_analyzer.analyze(query, [])

        dyn_top_k = analysis.top_k
        dyn_reranking = analysis.use_reranking
        dyn_expand = analysis.expand_context
        search_query = analysis.rewritten_query

        print(f"{Colors.DIM}🔍 Searching ({analysis.intent}, k={dyn_top_k})...{Colors.RESET}", end='\r')

        context = retriever.retrieve(
            query=search_query,
            top_k=dyn_top_k,
            date_start=analysis.date_start,
            date_end=analysis.date_end,
            use_reranking=dyn_reranking,
            expand_context=dyn_expand
        )

        if not context.has_results:
            print(f"{Colors.YELLOW}⚠️  No relevant documents found.{Colors.RESET}\n")
            sys.exit(0)

        # Display sources
        print_sources(context.results)

        # Generate response
        print(f"{Colors.BOLD}{Colors.GREEN}Assistant:{Colors.RESET} ", end='', flush=True)

        prompt = chatbot._build_prompt(query, context)

        # Response streaming
        response_text = ""
        for token in chatbot._chat_stream(query, prompt, context):
            print(token, end='', flush=True)
            response_text += token

        print("\n")

    except Exception as e:
        print(f"\n{Colors.RED}❌ Error: {e}{Colors.RESET}\n")
        sys.exit(1)


def print_stats(components):
    """Displays system statistics."""
    vector_store = components['vector_store']
    metadata_store = components.get('metadata_store')

    print(f"\n{Colors.BOLD}{Colors.CYAN}📊 System Statistics:{Colors.RESET}")
    print(f"  Indexed Chunks: {Colors.GREEN}{vector_store.size}{Colors.RESET}")

    if metadata_store:
        # Query to get conversation count
        cursor = metadata_store.conn.execute("SELECT COUNT(DISTINCT file_source) FROM chunks")
        conv_count = cursor.fetchone()[0]

        # Get date range
        cursor = metadata_store.conn.execute(
            "SELECT MIN(date_start), MAX(date_end) FROM chunks"
        )
        date_range = cursor.fetchone()

        print(f"  Conversations: {Colors.GREEN}{conv_count}{Colors.RESET}")
        if date_range[0] and date_range[1]:
            print(f"  Period: {Colors.GREEN}{date_range[0][:10]} → {date_range[1][:10]}{Colors.RESET}")

    print()


def main():
    """Main entry point."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Instagram Assistant - Chat CLI',
        add_help=False
    )
    parser.add_argument(
        '--prompt',
        type=str,
        help='Question to ask (non-interactive mode)'
    )
    parser.add_argument(
        '-h', '--help',
        action='store_true',
        help='Show help'
    )
    parser.add_argument(
        '--log-verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Initialize logging according to flag
    initialize_logging(args.log_verbose)

    if args.help:
        parser.print_help()
        print_help()
        sys.exit(0)

    if args.prompt:
        # Non-interactive mode: execute single question
        return main_noninteractive(args.prompt)

    print_header()

    # Initialization
    print(f"{Colors.YELLOW}⏳ Loading RAG system...{Colors.RESET}")

    try:
        config = Config()

        # Check if index exists
        if not (config.vector_store_path / "index.faiss").exists():
            print(f"\n{Colors.RED}❌ Error: FAISS index not found.{Colors.RESET}")
            print(f"{Colors.YELLOW}Please run setup_rag_batch.py first.{Colors.RESET}\n")
            sys.exit(1)

        # Load RAG components
        retriever, components = create_advanced_retriever(
            config,
            enable_reranking=True,
            enable_bm25=True,
            enable_metadata=True
        )

        # Create chatbot
        chatbot = ChatBot(retriever, config)
        query_analyzer = QueryAnalyzer(config)

        print(f"{Colors.GREEN}✅ System loaded ({components['vector_store'].size} chunks){Colors.RESET}\n")

    except Exception as e:
        print(f"\n{Colors.RED}❌ Error loading: {e}{Colors.RESET}\n")
        sys.exit(1)

    # Search options
    use_reranking = True
    use_hybrid = True
    expand_context = True

    # Main loop
    try:
        while True:
            try:
                # Ask question
                query = input(f"{Colors.BOLD}{Colors.BLUE}You:{Colors.RESET} ").strip()

                if not query:
                    continue

                # Special commands
                if query.lower() in ['exit', 'quit']:
                    print(f"\n{Colors.CYAN}👋 Goodbye!{Colors.RESET}\n")
                    break

                elif query.lower() == 'help':
                    print_help()
                    continue

                elif query.lower() == 'clear':
                    chatbot.conversation_history.clear()
                    print(f"{Colors.GREEN}✅ History cleared{Colors.RESET}\n")
                    continue

                elif query.lower() == 'stats':
                    print_stats(components)
                    continue

                elif query.lower().startswith('filters'):
                    parts = query.lower().split()
                    if len(parts) == 2:
                        if parts[1] == 'on':
                            use_reranking = use_hybrid = expand_context = True
                            print(f"{Colors.GREEN}✅ Advanced filters enabled{Colors.RESET}\n")
                        elif parts[1] == 'off':
                            use_reranking = use_hybrid = expand_context = False
                            print(f"{Colors.YELLOW}⚠️  Advanced filters disabled{Colors.RESET}\n")
                    continue

                # Search
                print(f"\n{Colors.DIM}🔍 Analyzing question...{Colors.RESET}", end='\r')
                analysis = query_analyzer.analyze(query, chatbot.conversation_history)
                
                dyn_top_k = analysis.top_k
                dyn_reranking = analysis.use_reranking
                dyn_expand = analysis.expand_context
                search_query = analysis.rewritten_query
                
                print(f"{Colors.DIM}🔍 Searching ({analysis.intent}, k={dyn_top_k})...{Colors.RESET}", end='\r')

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
                    print(f"{Colors.YELLOW}⚠️  No relevant documents found.{Colors.RESET}\n")
                    continue

                # Display sources
                print_sources(context.results)

                # Generate response
                print(f"{Colors.BOLD}{Colors.GREEN}Assistant:{Colors.RESET} ", end='', flush=True)

                prompt = chatbot._build_prompt(query, context)

                # Response streaming
                response_text = ""
                for token in chatbot._chat_stream(query, prompt, context):
                    print(token, end='', flush=True)
                    response_text += token

                print("\n")

            except KeyboardInterrupt:
                print(f"\n\n{Colors.YELLOW}Interrupted (Ctrl+C detected){Colors.RESET}")
                print(f"{Colors.DIM}Type 'exit' to quit or continue asking questions.{Colors.RESET}\n")
                continue

            except Exception as e:
                print(f"\n{Colors.RED}❌ Error: {e}{Colors.RESET}\n")
                continue

    except EOFError:
        # Ctrl+D
        print(f"\n\n{Colors.CYAN}👋 Goodbye!{Colors.RESET}\n")

    except Exception as e:
        print(f"\n{Colors.RED}❌ Fatal error: {e}{Colors.RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()