---
name: rag-debug-assistant
description: Diagnostic tool for Instagram Assistant RAG pipeline. Use when the user reports a bug, an infinite loop in the agent, or when the bot fails to find information that should be present. Helps analyze QueryAnalyzer output, Retrieval quality, and LLM generation steps.
---

# RAG Debug Assistant

This skill provides a structured workflow for diagnosing issues in the Instagram Assistant RAG pipeline.

## When to use

- **Agent Loops**: If the ReAct agent reaches max steps or repeats actions.
- **Retrieval Failures**: If the bot says "I don't know" for information that exists.
- **Malformed Output**: If the model (Ministral-3B) returns invalid JSON or corrupted text.
- **Unexpected Routing**: If a simple question triggers the complex agent path unnecessarily.

## Workflow

1. **Isolation**: Use the bundled `debug_query.py` script to reproduce the issue outside the full app.
2. **Analysis Check**: Verify if `QueryAnalyzer` correctly extracted the intent, rewritten query, and date range.
3. **Retrieval Check**: Verify if the `Retriever` found relevant chunks and what their scores are.
4. **Generation Check**: Verify if the `ChatBot` system prompt or context formatting is causing the issue.

## Using the Debug Script

Run the isolated debug script with the problematic query:

```bash
python3 rag-debug-assistant/scripts/debug_query.py "VOTRE QUESTION ICI"
```

If the issue involves conversation history:

```bash
python3 rag-debug-assistant/scripts/debug_query.py "QUESTION" --history '[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]'
```

## Common Fixes

- **Analyzer Issues**: Update `QUERY_ANALYSIS_PROMPT` or improve `repair_and_load_json` logic.
- **Retrieval Issues**: Adjust `top_k` values in `QueryAnalyzer._get_params_for_intent`.
- **Agent Loops**: Check `rag_pipeline/agent.py` parser or add "nudge" messages to the scratchpad.
- **Routing Issues**: Update `api/routing.py` logic.
