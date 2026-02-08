# Instagram Assistant - Agents

**Instagram Assistant** is a local, privacy-focused RAG (Retrieval-Augmented Generation) application for exploring and querying exported Instagram conversations.

**Package Managers:** `pip` (Backend), `pnpm` (Frontend)

## Overview

This project uses a multi-agent architecture where specialized LLMs handle specific stages of the pipeline.

| Agent | Role | Details |
|-------|------|---------|
| **[Enricher](docs/agents/01_enricher.md)** | **Indexing:** Extracts metadata, summaries, entities, and questions from chunks. | [Docs](docs/agents/01_enricher.md) |
| **[Summarizer](docs/agents/02_summarizer.md)** | **Indexing:** Generates hierarchical summaries (Conversation & Monthly). | [Docs](docs/agents/02_summarizer.md) |
| **[Analyzer](docs/agents/03_analyzer.md)** | **Query:** Interprets intent, rewrites queries, and routes logic. | [Docs](docs/agents/03_analyzer.md) |
| **[Chat Assistant](docs/agents/04_chat_assistant.md)** | **Query:** Generates the final answer based on retrieved context (fast-path). | [Docs](docs/agents/04_chat_assistant.md) |
| **[Evaluator](docs/agents/05_evaluator.md)** | **Evaluation:** Judges the quality of retrieval and generation. | [Docs](docs/agents/05_evaluator.md) |
| **[ReAct Agent](docs/agents/06_react_agent.md)** | **Query:** Multi-step reasoning with tool use, chronological timeline exploration, and evidence-based verification. | [Docs](docs/agents/06_react_agent.md) |

## Documentation Structure

For detailed instructions and prompt strategies, please refer to the individual agent files in `docs/agents/`.