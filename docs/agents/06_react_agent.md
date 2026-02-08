# ReAct Agent ("The Reasoner")

**Components:** `rag_pipeline/chat/agent.py`, `rag_pipeline/chat/tools.py`
**Trigger:** Binary router (`api/routing.py`) sends non-trivial queries here
**Default Model:** `ministral-8b`

The default execution path for complex queries. Uses the Thought -> Action -> Observation loop to decompose questions and call tools.

## Routing & Strategy

A deterministic binary router (`api/routing.py`) decides between two paths based on the `QueryAnalyzer` signals.

| Path | Condition | Description |
|------|-----------|-------------|
| **Fast-path** | `mode=retrieval` + `intent=specific_fact` | Direct retrieval pipeline, no agent overhead. |
| **Agent** | Everything else | ReAct loop with multi-step reasoning. |

### Why keep both? (Strategic Reasoning)

Maintaining a "Fast-path" alongside the ReAct agent is a deliberate architectural choice based on three pillars:

1.  **Latency (User Experience)**:
    *   **Fast-path**: Minimal steps (Analyzer -> Retrieval -> Generator). Ideal for immediate answers like "What is X's address?".
    *   **Agent**: Inherently slower due to sequential LLM calls (Thought -> Action -> Observation).
    *   **Goal**: Provide sub-5s responses for simple facts while reserving 10s+ reasoning for complex queries.

2.  **Resources & Cost (Token Efficiency)**:
    *   The ReAct loop is "token-hungry". Each iteration sends the entire "scratchpad" (reasoning history) back to the model.
    *   Using the Fast-path for simple queries significantly reduces GPU/CPU load on local Ollama instances and lowers costs for API-based models.

3.  **Reliability (Occam's Razor)**:
    *   **Simplicity = Robustness**. For a specific fact, a well-tuned retrieval engine (Dense + BM25) is more reliable than an agent that might "over-think" or hallucinate a complex tool chain for a simple fetch task.
    *   The Agent is the **Detective** (investigative), while the Fast-path is the **Sniper** (precise and fast).

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

## Tool Selection Strategy

L'agent ReAct ne se contente pas de chercher, il choisit l'outil le plus adapté selon la nature de la question pour maximiser la précision et minimiser les hallucinations :

*   **`search_conversations` (Le Généraliste)** :
    *   **Pourquoi ?** C'est le point d'entrée pour toute recherche de faits précis.
    *   **Usage Stratégique** : Utilisé avec des filtres JSON pour corriger l'analyseur si les premiers résultats sont trop larges ou concernent le mauvais participant.
*   **`get_thread_context` (L'Enquêteur)** :
    *   **Pourquoi ?** Le RAG classique tronque souvent les conversations au moment le plus intéressant.
    *   **Usage Stratégique** : Si l'agent trouve un message qui semble être le début d'une explication ("Je t'explique :"), il utilise cet outil pour "dérouler le fil" et obtenir la suite (+/- 5 messages) de manière ciblée.
*   **`check_entity_presence` (Le Garde-Fou)** :
    *   **Pourquoi ?** La recherche sémantique (vecteurs) peut parfois renvoyer des résultats "proches" mais qui ne contiennent pas le mot exact (ex: parle d'argent au lieu de Bitcoin).
    *   **Usage Stratégique** : Pour répondre avec certitude à "Ai-je déjà mentionné X ?", l'agent effectue une vérification stricte via BM25. Si cet outil ne trouve rien, l'agent peut affirmer l'absence du sujet.
*   **`explore_topic_timeline` (L'Historien)** :
    *   **Pourquoi ?** Répondre à "Combien de fois" ou "Comment ça a évolué" nécessite une vue macro.
    *   **Usage Stratégique** : Combine les résumés de périodes (épisodes) et les stats d'analytics pour construire une narration chronologique sans lire chaque message individuellement.
*   **`get_summaries_for_contact` (Le Profiler)** :
    *   **Pourquoi ?** Pour comprendre une relation longue, lire des chunks atomiques est inefficace.
    *   **Usage Stratégique** : Permet d'avoir une vue d'ensemble (dynamique relationnelle, thèmes récurrents) avant de plonger dans des recherches de détails.

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
