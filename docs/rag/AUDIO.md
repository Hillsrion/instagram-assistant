# Audio Transcription Integration

## Overview

This document describes the **Audio Transcription** module for the Instagram Assistant RAG pipeline.
Audio files from Instagram exports are transcribed using a local **MLX model** (Voxtral) and integrated as first-class text in the RAG index.

> **✅ STATUS: ACTIVE (Feb 2026)**
> Audio transcription now runs **locally on Apple Silicon** using MLX. No external server required.

## Architecture

```mermaid
graph LR
    A[Instagram Export] --> B(Audio Files .mp4/.m4a)
    B --> C[setup_transcriptions.py]
    C --> D[MLX Voxtral Model]
    D --> |Text| C
    C --> E[Audio Cache (JSON)]
    
    E --> F[instagram_to_text.py]
    F --> G[.txt files with transcriptions]
    G --> H[Chunker]
    H --> I[RAG Index]
    
    E --> J[setup_inject_audio.py]
    J --> |Post-process| H
```

## Components

### 1. MLX Audio Provider (`rag_pipeline/audio/mlx_audio_provider.py`)
- Uses `voxmlx` library with `mlx-community/Voxtral-Mini-4B-Realtime-6bit` model
- Automatically converts audio to WAV format via FFmpeg
- Handles streaming transcription with Metal acceleration

### 2. Audio Cache (`rag_pipeline/audio/audio_cache.py`)
- Persistent JSON key-value store: `Hash(file_path + size + mtime) → Transcription`
- Ensures each file is transcribed only once
- Located at `rag_data/audio_cache.json`

### 3. Batch Transcription (`scripts/setup/setup_transcriptions.py`)
- Scans `original_import_folders/**/audio/` for audio files
- Transcribes all files and populates the cache
- JSONL logging to `logs/setup_transcriptions.jsonl`
- ~4s per audio file on Apple Silicon

### 4. Audio Injection (`scripts/setup/setup_inject_audio.py`)
- **Post-hoc injection** for chunks created before transcription was available
- Replaces `[Audio]` placeholders with `[Audio: "transcription text"]`
- Marks modified chunks with `needs_reenrichment=True`
- Supports `--reenrich` flag to trigger enrichment on modified chunks

## Usage

### Option A: Include During Initial Indexing

```bash
# Run transcription first (long-running, ~12h for full dataset)
python scripts/setup/setup_rag.py --only transcribe

# Then run full pipeline (transcriptions will be embedded via instagram_to_text.py)
python scripts/setup/setup_rag.py
```

Or combine both:
```bash
python scripts/setup/setup_rag.py --with-transcribe
```

### Option B: Post-hoc Injection into Existing Chunks

If you already have indexed chunks without audio transcriptions:

```bash
# 1. Transcribe all audio files
python scripts/setup/setup_rag.py --only transcribe

# 2. Inject transcriptions into existing chunks
python scripts/setup/setup_rag.py --only inject_audio

# 3. Re-enrich modified chunks (optional)
python scripts/setup/setup_inject_audio.py --reenrich

# 4. Regenerate embeddings for modified chunks
python scripts/setup/setup_rag.py --only embed
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_AUDIO_TRANSCRIPTION` | `false` | Enable/disable audio transcription |
| `AUDIO_CACHE_PATH` | `rag_data/audio_cache.json` | Cache file location |

## Model Details

- **Model**: `mlx-community/Voxtral-Mini-4B-Realtime-6bit`
- **Framework**: MLX (Apple Silicon optimized)
- **Performance**: ~4 seconds per audio file on M1/M2/M3
- **Languages**: French, English (multilingual)
