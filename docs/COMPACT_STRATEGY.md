# RAG Pipeline Documentation

## Overview
This document outlines the core components and logic of the RAG (Retrieval-Augmented Generation) pipeline for the Instagram Assistant.

## 1. Indexing Strategy
The indexing process transforms raw conversation exports into searchable vector embeddings.

### Chunking
- **Semantic Chunking:** Conversations are split based on time gaps (> 2h) or size limits (max 50 messages/days).
- **Metadata Preservation:** Each chunk retains full context (participants, time range, original file source).

### ⚡ Compact Content Strategy (Optimization)
To improve embedding quality and reduce LLM token usage during enrichment, we implemented a **Content Compaction Strategy**.

#### Problem
Raw Instagram exports contain verbose metadata for every message:
```text
[2024-05-23 08:15] Lucas Chanavat • Photographe Lyon | Videaste | Drone: Salut !
[2024-05-23 08:16] Lucas Chanavat • Photographe Lyon | Videaste | Drone: Ça va ?
```
This introduces:
1.  **Noise in Embeddings:** The timestamp and job title dominate the vector, diluting the actual message content ("Salut", "Ça va").
2.  **High Token Cost:** Repeating long names and dates consumes ~40% of the context window sent to the LLM for enrichment.

#### Solution: `get_compact_content()`
We introduced a transformation layer that generates a streamlined version of the conversation **on the fly** for embeddings and enrichment. The original full content is preserved for storage and display.

**Transformation Rules:**
1.  **Strip Timestamps:** Removes `[YYYY-MM-DD HH:MM]`.
2.  **Shorten Names:**
    *   Uses **First Name** by default (e.g. `Lucas`).
    *   **Smart Disambiguation:** If multiple participants share a first name (e.g. "Lucie Dupont" and "Lucie Martin"), it automatically switches to `Firstname L.` format (e.g. `Lucie D.`, `Lucie M.`).
    *   **Special Characters & Emojis:** Preserves emojis (`🧡`) and fancy fonts (`𝓥𝓪𝓰𝓪𝓫𝓸𝓷𝓭𝓮`) correctly.
    *   **Edge Cases:**
        *   **Pipes (`|`):** `Elisa | Creator` → `Elisa` (Takes first word).
        *   **Slugs:** `lei.kam_` → `lei.kam_` (Preserved if no spaces).
        *   **Role-First:** `MAKEUP ARTIST - Ines` → `MAKEUP` (Limitation: always uses first word to ensure consistency).
3.  **Output Format:** `Name: Message`

#### Example
**Input (Raw):**
```text
[2024-05-23 08:15] Lucas Chanavat • Photographe Lyon | Videaste | Drone: Palalaaaa incroyable !!
[2024-05-23 08:16] Lucas Chanavat • Photographe Lyon | Videaste | Drone: Envoies 2-3 photos laaaaa
[2024-05-23 08:17] Ismaël: Mdrrr t'sais que je me faisais la remarque
[2024-05-23 08:17] 🧡: Love it!
```

**Output (Compact):**
```text
Lucas: Palalaaaa incroyable !!
Lucas: Envoies 2-3 photos laaaaa
Ismaël: Mdrrr t'sais que je me faisais la remarque
🧡: Love it!
```

#### Impact
| Component | Benefit |
|-----------|---------|
| **Embeddings** | Vectors now represent the *conversation semantics* (what was said) rather than the metadata (when/who). |
| **Enrichment** | **30-40% reduction in input tokens.** Faster processing and lower cost for LLM analysis. |
| **Retrieval** | No loss of information. The user still sees the full original message with precise timestamps in the app. |

## 2. Enrichment
(Enrichment details... see `docs/RAG_PIPELINE.md` for full context)
