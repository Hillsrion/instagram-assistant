# Embedding Strategy — Prioritization Hierarchy

## Objective

Build an embedding text that:
- Remains excellent on factual queries (dates, places, events, precise facts)
- Captures social and implicit aspects (tension, ghosting, relational dynamics)
- Avoids semantic dilution
- Works well with:
  - A general-purpose dense model (BGE-M3, 1024-dim)
  - Hybrid search (Dense + BM25, alpha=0.5)

---

## Fundamental Principle

**Everything encoded in the embedding must help answer a plausible user question.**

If information:
- Is not directly searchable
- Or doesn't help retrieve relevant passages

It should not be a priority in the embedding text.

---

## Priority Hierarchy (Strongest to Weakest Signal)

> **Note:** This hierarchy is a design hypothesis based on reasoning about how dense + BM25 hybrid search behaves. Star ratings reflect expected impact, not measured benchmarks. See [Limitations](#limitations--to-validate) below.

### Level 1 — Hypothetical Questions (Dominant Signal)

**Content:**
- 1 to N questions formulated as a user would ask them

**Examples:**
- "Pourquoi il a arrêté de répondre ?"
- "Quand est-ce qu'on a parlé de ce voyage ?"
- "Est-ce qu'il y a eu une dispute ?"

**Rationale:**
- Directly aligns query vector ↔ document vector
- Captures reformulations, synonyms, and implicit meanings (ghosting, discomfort, distance)
- Allows a small model to "understand usage" without reasoning

**Expected impact:** Very high on retrieval quality. Minimal risk of hurting factual queries since questions are additive.

**Dependency:** Quality entirely depends on the Enricher LLM. Poor questions = noise.

**Implementation:**
- Uses normalized repetition with `QUESTION_BUDGET` (from `default_config.max_questions`)
- Tagged as `[QUESTION]`

---

### Level 2 — Narrative Summary

**Content:**
- 1 sentence: action + intention + result

**Rationale:**
- Dense semantic condensation of the chunk's meaning
- Helps the dense retriever on broad/vague queries ("qu'est-ce qui s'est passé avec X ?")
- Concise by nature (1 sentence) — small token footprint, no need for repetition

**Expected impact:** Moderate on retrieval, useful as semantic backup for the reranker.

**Implementation:**
- Tagged as `[SUMMARY]`
- x1 occurrence (concise by design)

---

### Level 3 — Explicit Entities (Hard Facts)

**Content:**
- Places, people mentioned, media, events

**Rationale:**
- Factual anchors with zero interpretation
- Dense + BM25 mutually reinforce here

**Rule:**
- EXPLICIT ONLY — no inference
- Keep the list short

**Why x1 (not x2):** BM25 already catches exact entity terms from the raw content at the bottom of the embedding text. Doubling entities in the dense portion risks diluting other signals when a chunk has many entities (10+ entities = 20+ lines with x2).

**Expected impact:** Very high on factual questions. Protects against semantic drift.

**Implementation:**
- Tagged by category: `[ENTITY:locations]`, `[ENTITY:people]`, etc.
- x1 occurrence per entity

---

### Level 4 — Semantic Temporal Context

**Content:**
- "avant le déménagement"
- "pendant les vacances"
- "après la dispute"

**Rationale:**
- Humans rarely ask with ISO dates
- Time is often relational, not calendrical

**Expected impact:** High for temporal queries ("à cette période", "au début", "à ce moment-là").

**Implementation:**
- Tagged as `[TIME]`
- x1 occurrence

---

### Level 5 — Participant Intentions

**Content:**
- Main objective per participant

**Examples:**
- "clarifier la relation"
- "éviter le conflit"
- "organiser une rencontre"

**Rationale:**
- Bridges factual and social
- Improves queries like: "qu'est-ce qu'il voulait ?", "qui poussait pour se voir ?"

**Expected impact:** Moderate. Keep concise.

**Implementation:**
- Tagged as `[INTENT]`
- Format: `{participant}: {intent}`

---

### Level 6 — Emotions & Tension (Weak but Targeted Signal)

**Content:**
- Dominant emotion, tone, tension level (low / medium / high)

**Rationale:**
- Useful for "ça s'est mal passé ?", "est-ce que c'était tendu ?"
- Tension = social fact, not opinion

**Rules:**
- 1 line max
- Controlled vocabulary (the Enricher prompt constrains output to a fixed set)
- Never repeated

**Expected impact:** Low on general retrieval, but targeted for emotional queries. No negative impact if concise.

**Implementation:**
- Tagged as `[EMOTION]`
- Format: `{dominant} | {tone} | tension:{level}`

---

### Level 7 — Social Dynamics (Specialized Signal)

**Content:**
- `interaction_pattern` — type of exchange (Planning, Debate, Support...)
- `initiative` — who leads the conversation
- `emotional_shift` — trajectory (e.g. "Neutral -> Happy")
- `open_loops` — unresolved topics

**Rationale:**
- Essential for ghosting detection, avoidance patterns, relational imbalance
- Not critical for pure factual search

**Golden Rule:**

> Social dynamics should never be more voluminous than the summary.

**Expected impact:** Low on factual queries. High on relational analysis.

**Implementation:**
- Tagged as `[INITIATIVE]`, `[OPEN_LOOP]`, `[INTERACTION]`, `[EMOTIONAL_SHIFT]`
- x1 occurrence each

---

### Level 8 — Raw Content (BM25 Primary Signal)

**Content:**
- Original messages (compact version via `get_compact_content()`)

**Rationale:**
- **This is NOT a safety net.** With hybrid search at alpha=0.5, BM25 contributes 50% of the retrieval score. Raw content IS BM25's primary signal.
- Also provides: reranker context, exact citation source

**Implementation:**
- Tagged as `[CONTENT]`
- Uses compact content (see [COMPACT_STRATEGY.md](COMPACT_STRATEGY.md))
- Always present, always last

---

## Design Decisions & Trade-offs

### Why no repetition on entities (x1 vs previous x2)

The previous approach doubled every entity line. With chunks containing 10+ entities across 4 categories, this created 20+ lines that could dominate the embedding space. Since BM25 already performs exact term matching on the raw content, the dense model only needs entities once to capture semantic associations.

### Why summary moved to level 2

Previously at level 5 (after entities and temporal context). Moved up because:
1. It's the densest semantic signal per token (1 sentence capturing the full chunk meaning)
2. Helps with broad queries that don't target specific entities or dates
3. Small token footprint — doesn't displace other signals

### Why raw content is not a "backup"

In a hybrid system at alpha=0.5, BM25 is co-equal with dense search. The raw content is BM25's entire input. Framing it as a "safety net" understates its importance — it's half the retrieval system.

### Position vs. Volume

BGE-M3 encodes the full text into a single vector. Position in the text matters less than token volume. The hierarchy controls weight primarily through:
- **Budget normalization** (questions)
- **Repetition count** (x1 for most fields)
- **Presence/absence** of fields

---

## Special Case: Ghosting / Social Patterns

### Why This Doesn't Hurt Factual Queries

Ghosting is **not** a single field. It's an **emergent pattern** from:
- Open loops (unresolved topics left hanging)
- Imbalanced initiative (one person always initiating)
- Emotional shift (warmth → distance)
- Hypothetical questions ("pourquoi il a arrêté de répondre ?")

The factual layer (dates, messages, silences) remains intact. The social layer doesn't add noise — it provides a reading.

---

## Anti-Patterns

- **Do not encode** arbitrary scores, unjustified subjective labels, long analyses, or diagnoses ("manipulation", "toxic")
- **Do not repeat** emotions/tension in every field
- **Do not make** social dynamics the core of the vector
- **Do not add** inferred entities — only explicitly mentioned ones

---

## Limitations & To Validate

This strategy is based on design reasoning, not empirical benchmarks. Key assumptions to validate:

1. **Hypothetical question quality** — If the Enricher (ministral-8b) generates generic or off-target questions, Level 1 becomes noise. Should be tested with/without questions to measure retrieval delta.

2. **Entity x1 vs x2** — The switch from x2 to x1 reduces entity emphasis. If factual recall drops on entity-heavy queries, consider restoring x2 with a cap (e.g. max 10 entity lines total).

3. **Summary at level 2** — This is a bet on broad query performance. If specific factual queries regress, summary can be moved back down.

4. **Token budget** — BGE-M3 accepts up to 8192 tokens. With long conversations + all enrichment fields, there may be truncation. No measurement exists yet on typical embedding text lengths.

5. **Star ratings** — The impact ratings in this document are qualitative estimates, not measured values. An A/B eval comparing retrieval with different field configurations would provide actual numbers.

---

## Implementation Reference

See `rag_pipeline/chunker.py::Chunk.get_embedding_text()` for the implementation.

The method builds the embedding text by:
1. Hypothetical questions with budget normalization
2. Narrative summary (x1)
3. Entities (x1 per entity)
4. Temporal context, intents (x1 each)
5. Structural dynamics: initiative, open loops (x1 each)
6. Emotional/social fields (x1 each)
7. Compact raw content (single pass)
