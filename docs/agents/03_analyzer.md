# Analyzer Agent ("The Dispatcher")

**Component:** `rag_pipeline/query/query_analyzer.py`
**Trigger:** Start of every user query
**Default Model:** `ministral-8b`

This is the "Brain" of the real-time pipeline. It decides *how* to answer a question before any search is done.

## Capabilities ("Omni-Prompt")

It performs 4 tasks in a SINGLE LLM call to reduce latency:

1.  **Routing (Mode Detection):**
    *   `analytics`: for counting/listing questions (e.g., "How many messages with X?").
    *   `retrieval`: for factual questions (e.g., "What did X say about Y?").
2.  **Query Rewriting:** Transforms vague questions (e.g., "what about him?") into standalone search queries ("What about [Name] in [Context]?").
3.  **Intent Classification:**
    *   `specific_fact`: Needs precise recall.
    *   `broad_summary`: Needs general overview.
    *   `complex_reasoning`: Needs high retrieval depth.
4.  **Date Extraction:** Extracts ISO date ranges from natural language (e.g., "last summer").

## Downstream: Binary Router

The Analyzer's `mode` and `intent` feed a deterministic binary router (`api/routing.py`):

- **Fast-path** (`mode=retrieval` + `intent=specific_fact`): direct retrieval pipeline, no agent.
- **Agent path** (everything else): ReAct Agent with tool use. See [ReAct Agent](06_react_agent.md).
