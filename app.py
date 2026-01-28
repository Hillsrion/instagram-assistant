#!/usr/bin/env python3
"""
Instagram Conversations Assistant - Web Application
FastAPI backend with modern chat interface.

This is the main entry point. The actual API logic is now in the 'api/' package.
"""
from api import app
from rag_pipeline.logger import initialize_logging


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description='Instagram Assistant - Web API')
    parser.add_argument(
        '--log-verbose',
        action='store_true',
        help='Activer les logs détaillés'
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host address'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port number'
    )

    args = parser.parse_args()

    # Initialiser le logging selon le flag
    initialize_logging(args.log_verbose)

    uvicorn.run(app, host=args.host, port=args.port)
