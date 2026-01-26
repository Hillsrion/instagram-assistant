# Instagram Conversations Assistant

Assistant IA local pour explorer et interroger vos conversations Instagram exportées.

## Fonctionnalités

- **RAG avancé** : Recherche hybride (dense + BM25), reranking cross-encoder, context expansion
- **Interface web moderne** : Conversations multiples, filtres, streaming
- **100% local** : Aucune donnée envoyée sur Internet
- **562k+ messages** indexés et recherchables

## Quickstart

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Indexer les conversations (première fois uniquement)
python3 setup_rag_batch.py

# 3. Lancer l'application web
python3 app.py

# 4. Ouvrir http://localhost:8000
```

## Architecture

```
instagram_conversations/     # 1218 conversations exportées
rag_data/
  ├── chunks.json           # 43k chunks avec métadonnées
  ├── faiss_index/          # Index vectoriel (dense search)
  ├── bm25_index.pkl        # Index lexical (keyword search)
  └── metadata.db           # SQLite (filtrage rapide)
rag_pipeline/               # Modules du pipeline RAG
web/                        # Interface web
app.py                      # Serveur FastAPI
```

## Commandes utiles

```bash
# Voir l'état de l'indexation
python3 setup_rag_batch.py --status

# Réindexer depuis zéro
python3 setup_rag_batch.py --reset

# Chat CLI (sans interface web)
python3 chat_instagram_advanced.py
```

## Filtres disponibles

Dans l'interface ou le CLI, vous pouvez filtrer par :
- `@nom` : Participant
- `#2023` : Année
- `[2023-01:2023-06]` : Période

Exemple : "de quoi on a parlé @pauline #2023 ?"

## Stack technique

- **Embeddings** : BGE-M3 (multilingue FR/EN)
- **Vector Store** : FAISS
- **Reranker** : BGE-reranker-base
- **LLM** : Ollama (Qwen3)
- **Backend** : FastAPI
- **Frontend** : HTML/CSS/JS (Vanilla)

## Confidentialité

Tout fonctionne en local :
- Modèles téléchargés une seule fois
- Aucune API externe
- Données stockées uniquement sur votre machine
