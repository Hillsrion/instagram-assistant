# Compact Content Strategy

## Problem

Raw Instagram exports contain verbose metadata for every message:
```text
[2024-05-23 08:15] Lucas Chanavat • Photographe Lyon | Videaste | Drone: Salut !
[2024-05-23 08:16] Lucas Chanavat • Photographe Lyon | Videaste | Drone: Ça va ?
```
This introduces:
1. **Noise in Embeddings:** The timestamp and job title dominate the vector, diluting the actual message content ("Salut", "Ça va").
2. **High Token Cost:** Repeating long names and dates consumes ~40% of the context window sent to the LLM for enrichment.

## Solution: `get_compact_content()`

A transformation layer that generates a streamlined version of the conversation **on the fly** for embeddings and enrichment. The original full content is preserved for storage and display.

**Transformation Rules:**
1. **Strip Timestamps:** Removes `[YYYY-MM-DD HH:MM]`.
2. **Shorten Names:**
   - Uses **First Name** by default (e.g. `Lucas`).
   - **Smart Disambiguation:** If multiple participants share a first name (e.g. "Lucie Dupont" and "Lucie Martin"), it automatically switches to `Firstname L.` format (e.g. `Lucie D.`, `Lucie M.`).
   - **Special Characters & Emojis:** Preserves emojis (`🧡`) and fancy fonts (`𝓥𝓪𝓰𝓪𝓫𝓸𝓷𝓭𝓮`) correctly.
   - **Edge Cases:**
     - **Pipes (`|`):** `Elisa | Creator` → `Elisa` (Takes first word).
     - **Slugs:** `lei.kam_` → `lei.kam_` (Preserved if no spaces).
     - **Role-First:** `MAKEUP ARTIST - Ines` → `MAKEUP` (Limitation: always uses first word to ensure consistency).
3. **Output Format:** `Name: Message`

## Example

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

## Impact

| Component | Benefit |
|-----------|---------|
| **Embeddings** | Vectors represent *conversation semantics* (what was said) rather than metadata (when/who). |
| **Enrichment** | **30-40% reduction in input tokens.** Faster processing for LLM analysis. |
| **Retrieval** | No loss of information. The user still sees the full original message with precise timestamps in the app. |

## Implementation Reference

See `rag_pipeline/indexing/chunker.py::Chunk.get_compact_content()`.

Used by `get_embedding_text()` as the raw content layer (Level 8 in [EMBEDDING_STRATEGY.md](EMBEDDING_STRATEGY.md)).
