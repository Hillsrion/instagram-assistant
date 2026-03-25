# Documentation Map

Welcome to the **Sira** documentation. This directory is organized to help you find information based on your current need, whether you are setting up the project, understanding the architecture, or deep-diving into the RAG pipeline.

## 🚀 Getting Started
*   **[QUICKSTART.md](QUICKSTART.md)**: The fastest way to get the project running.
*   **[COMMANDS.md](COMMANDS.md)**: Cheat sheet (Makefile, scripts) for building, running, and testing.
*   **[CONFIGURATION.md](CONFIGURATION.md)**: Environment variables (`.env`) and system settings.

## 🏗 System Architecture
*   **[ARCHITECTURE.md](ARCHITECTURE.md)**: High-level overview of system modules, data flow, and tech stack.
*   **[FEATURES.md](FEATURES.md)**: Detailed breakdown of implemented features and capabilities.
*   **[API.md](API.md)**: Documentation of the FastAPI endpoints and backend interfaces.

## 🧠 RAG Pipeline (Core Logic)
The Retrieval-Augmented Generation system is complex, so its documentation is centralized in a dedicated directory:
*   **[📂 rag/README.md](rag/README.md)**: **Start here for RAG.** Index of strategies, pipeline details, and enrichment docs.
    *   Contains: Pipeline architecture, Embedding strategies, and Parallel enrichment guides.

## 🛠 Development & Development
*   **[DEVELOPMENT.md](DEVELOPMENT.md)**: Guidelines for contributing, code workflow, and setup.
*   **[LOGGING_GUIDE.md](LOGGING_GUIDE.md)**: How to use and interpret the logging system.
*   **[PROPOSED_IMPROVEMENTS.md](PROPOSED_IMPROVEMENTS.md)**: Roadmap and future enhancement ideas.

## 🤖 Agents & Evaluation
*   **[EVAL.md](EVAL.md)**: How to run evaluations and interpret metrics.
*   **[agents/](agents/)**: Configuration and prompts for specific agents (Summarizer, Enricher, etc.).
*   **[eval/](eval/)**: Evaluation scripts and datasets.
