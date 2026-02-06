# Audio Integration (Postponed)

## Overview
This document describes the **Audio Dialogues Integration** strategy for the Instagram Assistant RAG pipeline.
The goal is to transcribe audio files from Instagram exports and treat them as first-class text citizens in the RAG index.

> **⚠️ STATUS: POSTPONED (Feb 2026)**
> The codebase contains all necessary logic (Cache, Client, Scripts), but the **Transcription Server (VLLM)** cannot currently run natively on macOS due to critical dependency conflicts (Torch/Numpy).
> **Recommendation**: Run the VLLM server via Docker or an external GPU machine.

## Architecture: "Upstream Caching"

We use an **Upstream Caching** strategy to decouple the heavy transcription process from the indexing pipeline.

```mermaid
graph LR
    A[Instagram Export] --> B(Audio Files .mp4/.m4a)
    B --> C[Batch Transcriber]
    C -->|API Calls| D[VLLM Audio Server]
    D -->|Text| C
    C --> E[Audio Cache (JSON)]
    
    start[setup_rag.py] --> F[InstagramToText]
    F -->|Read| E
    F --> G[Enriched Text]
    G --> H[Chunker]
    H --> I[RAG Index]
```

### Components

1.  **Audio Server (`scripts/start_audio_server.sh`)**
    *   Runs an OpenAI-compatible server using `vllm`.
    *   Model: `mistralai/Voxtral-Mini-4B-Realtime-2602`.
    *   **Port**: 8001 (to avoid conflict with main app on 8000).

2.  **Batch Transcriber (`scripts/transcribe_all.py`)**
    *   Scans the export directory for audio files.
    *   Sends them to the local server (Port 8001).
    *   Saves results to `rag_data/audio_cache.json` (or configured path).

3.  **Audio Cache (`rag_pipeline/audio_cache.py`)**
    *   A persistent JSON Key-Value store (`Hash(FileContent) -> Transcription`).
    *   Ensures we never transcribe the same file twice.

4.  **Ingestion (`scripts/ingestion/instagram_to_text.py`)**
    *   Updated to check the cache when encountering audio files.
    *   If cache hit: Inserts transcription text into the conversation log.
    *   If cache miss: Leaves `[Audio]` placeholder (doesn't block).

## Why Postponed? (Technical Note)

As of Feb 2026, running **VLLM** with **Voxtral** on **macOS (Apple Silicon)** faces a dependency hell:
1.  **Voxtral** requires RoPE scaling support in VLLM.
2.  **Stable VLLM (0.14.x)** does not support this RoPE config for Whisper models.
3.  **Dev VLLM** requires `torch >= 2.9 (Nightly)`.
4.  **Torch Nightly (2.10)** on macOS is currently broken (missing `_C_utils` symbols).

**Solution**: The code valid and merged to `dev`. To activate it, simply run the VLLM server in a **Docker container** (Linux environment) where these dependencies are stable.

## How to Resume

1.  **Start VLLM (Docker/Linux)**:
    Launch a VLLM container exposing port 8001.
    ```bash
    # Example (Conceptual)
    docker run --gpus all -p 8001:8000 vllm/vllm-openai ...
    ```

2.  **Run Transcription**:
    ```bash
    python scripts/transcribe_all.py
    ```

3.  **Re-index**:
    ```bash
    python scripts/setup/setup_rag.py
    ```
