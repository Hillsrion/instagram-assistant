# ReAct Agent ("The Reasoner")

**Components:** `rag_pipeline/chat/agent.py`, `rag_pipeline/chat/tools.py`
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

The ToolBox implements the ReAct agent's capabilities. Tools support both simple string inputs and JSON-formatted multi-argument inputs (e.g., `{"query": "X", "participant": "Y"}`).

| Tool | Signature | Description |
|------|-----------|-------------|
| `search_conversations` | `(query, participant?, date_range?)` | **Enhanced:** Full retrieval pipeline. Supports forced participant/date filtering to correct analyzer errors. |
| `explore_topic_timeline`| `(query)` | **Enhanced:** Chronological analysis across summaries and chunks. Includes **monthly activity volume** from analytics. |
| `get_thread_context` | `(chunk_id, window=5)` | **New:** Surgically expands context around a specific message to understand the flow of a conversation. |
| `check_entity_presence` | `(keyword, participant?)` | **New:** Strict BM25/keyword verification. Anti-hallucination tool to confirm if a specific term was actually mentioned. |
| `get_summaries_for_contact` | `(contact, limit=5)` | **New:** High-level overview of the most recent conversations/periods with a specific person. |
| `get_contact_stats` | `(contact_name)` | Message count, conversation count, activity period via analytics module. |
| `get_participants` | `()` | Lists all participants with statistics. |
| `get_todays_date` | `()` | Current date for temporal reasoning. |

## Pipeline Integration

- **Multi-argument Support:** Tools can be called with JSON inputs, permettant à l'agent d'effectuer des recherches filtrées complexes.
- **Analysis injection:** The `AnalysisResult` from the Analyzer is passed to the ToolBox so tools use the correct defaults, which can be overridden by the agent.
- **Identity Awareness:** The agent is aware of the user's name. It understands that messages from this person are from the user.
- **Smart fallback:** If the rewritten query yields low-confidence results, the original user query is tried automatically.
- **Source extraction:** After the agent loop, sources are extracted from the last retrieval context and returned to the frontend.
- **Fallback Synthesis:** If the agent reaches `max_steps` or fails, a final synthesis step is performed using the accumulated "scratchpad".
- **Conversation history:** The last 4 turns of conversation are included in the agent prompt for context continuity.

## System Prompt

Located in `AGENT_SYSTEM_PROMPT`. Key rules:
- **Strict Format:** `Thought:` / `Action:` / `Action Input:` / `Observation:` / `Final Answer:`
- **Multi-argument Inputs:** Uses `{"arg": "val"}` JSON for tools like `search_conversations`.
- **Deep Dive:** Uses `get_thread_context` if a search result seems incomplete or truncated.
- **Verification:** Uses `check_entity_presence` for strict confirmation of specific keywords.
- **Overview:** Uses `get_summaries_for_contact` for rapid top-down understanding.
- **Chronology first:** Use `explore_topic_timeline` for temporal or quantitative queries.
- Maximum 10 reasoning steps.

## SSE Event Mapping

Agent events are translated to the same SSE format the frontend already understands:

| Agent Event | SSE Event |
|-------------|-----------|
| `thought` | `progress` (step: thinking) |
| `action` | `progress` (step: search) |
| `observation` | `progress` (step: documents) |
| `final` | `chunk` + `sources` |
