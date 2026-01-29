# Potential Future Improvements

## Search Strategies

### Parallel Hybrid Search (Proactive) 🚀

This is an advanced strategy to handle abrupt context changes without latency, proposed to replace or complement the "Smart Fallback".

**The Problem:**
Currently, if the `QueryAnalyzer` rewrites a query by adding too much context (e.g., "Bills" becomes "Bills with Ayoub"), the search fails if the user was talking about something else. The current "Smart Fallback" fixes this but potentially adds latency (2 sequential searches in case of failure).

**The Solution: "Parallel Execution + Reciprocal Rank Fusion (RRF)"**

Instead of waiting for the first search to fail, the system **always** launches two searches in parallel:

1.  **Contextual Branch:** Search with the query rewritten by the LLM (Optimized for conversation follow-up).
2.  **Raw Branch:** Search with the original user query (Optimized for topic change).

**Fusion Algorithm (RRF):**
We combine the results from both branches.
- If a document appears in both lists, its score increases significantly.
- If a document appears only in the "Raw" branch (because the topic changed) with a high score, it naturally rises to the top of the list, surpassing weak results from the contextual branch.

**Advantages:**
*   **Fluid User Experience:** Constant latency, no "double" wait visible to the user.
*   **Maximum Robustness:** Automatically and implicitly handles ambiguity between "Same topic" and "New topic" without complex heuristics.

**Disadvantages:**
*   **Computational Cost:** Doubles the number of vector searches (embeddings + search) per user message.

**Technical Implementation Paths:**
*   Use `asyncio.gather` in `app.py` to launch both `retriever.retrieve()` calls simultaneously.
*   Implement a standard RRF fusion function (e.g., `score = 1 / (rank + k)`) or a weighted average of similarity scores.