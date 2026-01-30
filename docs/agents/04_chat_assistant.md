# Chat Assistant Agent ("The Speaker")

**Component:** `rag_pipeline/chat.py`
**Trigger:** After retrieval
**Default Model:** `ministral-8b`

The final interface that talks to the user.

## Responsibility

- Reads the retrieved documents (Detailed Chunks + Global Summaries).
- Synthesizes an answer.
- **Strictly Anti-Hallucination:** System prompt explicitly forbids using outside knowledge.

## Key Features

- **Context Awareness:** It receives both "Micro" clues (exact messages) and "Macro" clues (summaries) in its context window.
- **Follow-up Generation:** Uses a separate lighter prompt (`FOLLOWUP_PROMPT`) to suggest 3 next questions.
- **History Compacting:** Automatically summarizes its own conversation history when it gets too long.

## System Prompt

Located in `SYSTEM_PROMPT`. Key rules include:
- "VERACITY - Answer ONLY from provided documents"
- "NO CITATIONS - Do not list Source IDs"
- "PRIVACY - Do not reveal PII"
