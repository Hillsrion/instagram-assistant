# RAG Documentation Index

This directory contains detailed specific documentation for the Retrieval-Augmented Generation (RAG) system of the Instagram Assistant.

## Core Architecture
- **[RAG_PIPELINE.md](RAG_PIPELINE.md)**: The central source of truth for the RAG pipeline. Details the indexing phases (Chunking, Enrichment, Embedding, Indexing) and the Query/Search phases.

## Indexing & Embedding Strategies
- **[EMBEDDING_STRATEGY.md](EMBEDDING_STRATEGY.md)**: Explains the logic behind embedding generation, including how we handle different types of content and metadata weighting.
- **[ENRICHMENT_STRATEGY.md](ENRICHMENT_STRATEGY.md)**: Details the model selection strategy (3B vs 8B) and complexity routing logic for chunk enrichment.
- **[COMPACT_STRATEGY.md](COMPACT_STRATEGY.md)**: Details the strategy for creating "compact" chunks to optimize context window usage while preserving semantic meaning.

## Audio Integration (Experimental / Postponed)
- **[AUDIO.md](AUDIO.md)**: Strategy for transcribing and indexing audio files (currently postponed due to server dependencies).

## Distributed Enrichment (Performance)
- **[PARALLEL_ENRICHMENT_QUICKSTART.md](PARALLEL_ENRICHMENT_QUICKSTART.md)**: A quick guide for running the enrichment process in parallel to speed up indexing.
- **[README_PARALLEL_ENRICHMENT.md](README_PARALLEL_ENRICHMENT.md)**: Comprehensive documentation on the parallel/distributed enrichment system architecture and usage.
- **[DISTRIBUTED_ENRICHMENT.md](DISTRIBUTED_ENRICHMENT.md)**: Deep dive into the distributed computing aspects of the enrichment pipeline.

## Evaluation & Statistics
- **[TOP_K_ANALYSIS_REPORT.md](TOP_K_ANALYSIS_REPORT.md)**: Analysis of retrieval performance with different 'k' values.
- **[TOP_K_STATISTICS.md](TOP_K_STATISTICS.md)**: Raw statistics and data points supporting the Top-K analysis.
