# Documentation Instagram Assistant

Bienvenue dans la documentation de l'Instagram Assistant, un système RAG (Retrieval-Augmented Generation) pour analyser vos conversations Instagram.

## Documents

| Document | Description |
|----------|-------------|
| [Guide de démarrage rapide](QUICKSTART.md) | Installation et premiers pas |
| [Fonctionnalités](FEATURES.md) | Documentation complète des fonctionnalités |
| [Référence API](API.md) | Endpoints REST et événements SSE |

## Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────┐
│                     Instagram Assistant                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Web UI     │    │     CLI      │    │     API      │       │
│  │  (index.html)│    │   (cli.py)   │    │   (app.py)   │       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘       │
│         │                   │                   │                │
│         └───────────────────┴───────────────────┘                │
│                             │                                    │
│                    ┌────────▼────────┐                           │
│                    │    ChatBot      │                           │
│                    │  (chat.py)      │                           │
│                    └────────┬────────┘                           │
│                             │                                    │
│         ┌───────────────────┼───────────────────┐                │
│         │                   │                   │                │
│  ┌──────▼──────┐    ┌───────▼───────┐   ┌──────▼──────┐         │
│  │   Retriever │    │  PII Filter   │   │   Followup  │         │
│  │  (advanced) │    │               │   │  Generator  │         │
│  └──────┬──────┘    └───────────────┘   └─────────────┘         │
│         │                                                        │
│  ┌──────┴─────────────────────────────────┐                     │
│  │                                         │                     │
│  │  ┌─────────┐ ┌─────────┐ ┌──────────┐  │                     │
│  │  │  FAISS  │ │  BM25   │ │ Metadata │  │                     │
│  │  │  Index  │ │  Index  │ │  Store   │  │                     │
│  │  └─────────┘ └─────────┘ └──────────┘  │                     │
│  │                                         │                     │
│  │         Vector Store + Indices          │                     │
│  └─────────────────────────────────────────┘                     │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                     Outils auxiliaires                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ Delta Tracker│ │  Evaluator   │ │   Enricher   │             │
│  │              │ │  (RAGAS)     │ │   (LLM)      │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## Fonctionnalités principales

### 1. Recherche hybride
- Recherche dense (embeddings FAISS)
- Recherche lexicale (BM25)
- Reranking cross-encoder
- Expansion de contexte

### 2. Robustesse
- Seuil de confiance configurable
- Filtrage PII automatique
- Prompts anti-hallucination

### 3. Mises à jour incrémentales
- Détection automatique des changements
- Indexation partielle (ajout/modification/suppression)
- État persistant

### 4. Évaluation automatisée
- Génération de données synthétiques
- Métriques RAGAS (Accuracy, MRR, Faithfulness)
- Comparaison de configurations

### 5. UX avancée
- Streaming avec indicateurs de progression
- Citations interactives (modal de détail)
- Questions de suivi générées

## Technologies

| Composant | Technologie |
|-----------|-------------|
| Backend | FastAPI, Python 3.10+ |
| LLM | Ollama (local) |
| Embeddings | BGE-M3 (multilingual) |
| Vector Store | FAISS |
| BM25 | rank_bm25 |
| Reranker | BGE-reranker-base |
| Frontend | Vanilla JS, CSS |

## Licence

MIT
