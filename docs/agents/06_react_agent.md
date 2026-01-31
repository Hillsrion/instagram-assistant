# ReAct Agent ("The Reasoner")

**Components:** `rag_pipeline/agent.py`, `rag_pipeline/tools.py`
**Trigger:** Binary router (`api/routing.py`) sends non-trivial queries here
**Default Model:** `ministral-8b`

The default execution path for complex queries. Uses the Thought -> Action -> Observation loop to decompose questions and call tools.

## Routing

A deterministic binary router (`api/routing.py`) decides between two paths:

| Path | Condition | Description |
|------|-----------|-------------|
| **Fast-path** | `mode=retrieval` + `intent=specific_fact` | Direct retrieval pipeline, no agent overhead |
| **Agent** | Everything else | ReAct loop with tool use |

The router uses signals from the Analyzer agent (mode, intent) — no additional LLM call.

## Tools (ToolBox)

| Tool | Signature | Description |
|------|-----------|-------------|
| `search_conversations` | `(query: str)` | Full retrieval pipeline: hybrid search, reranking, date filters, smart fallback |
| `get_contact_stats` | `(contact_name: str)` | Message count, conversation count, activity period via analytics module |
| `get_participants` | `()` | Lists all participants with statistics |
| `get_todays_date` | `()` | Current date in ISO format |

All tools wrap the same pipeline components used by the fast-path. There is no divergent retrieval logic.

## Pipeline Integration

- **Analysis injection:** The `AnalysisResult` from the Analyzer is passed to the ToolBox so `search_conversations` uses the correct `top_k`, reranking, date filters, and expand settings.
- **Smart fallback:** If the rewritten query yields low-confidence results, the original user query is tried automatically.
- **Source extraction:** After the agent loop, sources are extracted from the last retrieval context and returned to the frontend.
- **Conversation history:** The last 4 turns of conversation are included in the agent prompt for context continuity.

## System Prompt

Located in `AGENT_SYSTEM_PROMPT`. Key rules:
- Strict ReAct format: `Thought:` / `Action:` / `Action Input:` / `Observation:` / `Final Answer:`
- Never guess information — always use tools
- Use `get_contact_stats` for counting, `get_participants` for listing
- Maximum 5 reasoning steps

## SSE Event Mapping

Agent events are translated to the same SSE format the frontend already understands:

| Agent Event | SSE Event |
|-------------|-----------|
| `thought` | `progress` (step: thinking) |
| `action` | `progress` (step: search) |
| `observation` | `progress` (step: documents) |
| `final` | `chunk` + `sources` |
