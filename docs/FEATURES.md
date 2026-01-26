# Instagram Assistant - Documentation des Fonctionnalités

Ce document décrit les fonctionnalités avancées du système RAG Instagram Assistant.

---

## Table des matières

1. [Pipeline d'Évaluation](#1-pipeline-dévaluation)
2. [Robustesse et Confiance](#2-robustesse-et-confiance)
3. [Mises à jour Incrémentales](#3-mises-à-jour-incrémentales)
4. [Expérience Utilisateur](#4-expérience-utilisateur)

---

## 1. Pipeline d'Évaluation

Le pipeline d'évaluation permet de mesurer et comparer les performances du système RAG de manière automatisée.

### 1.1 Génération de données synthétiques

Le module `eval/synthetic_generator.py` génère automatiquement des paires question-réponse à partir des chunks indexés.

#### Types de questions générées

| Type | Description | Exemple |
|------|-------------|---------|
| `factual` | Extraction directe d'information | "Quand avez-vous parlé de X ?" |
| `summary` | Question de synthèse | "De quoi avez-vous discuté en janvier ?" |
| `implicit` | Inférence légère | "Quelle était l'ambiance de cette conversation ?" |
| `temporal` | Questions temporelles | "À quelle période avez-vous planifié Y ?" |

#### Utilisation

```python
from eval.synthetic_generator import SyntheticDataGenerator

generator = SyntheticDataGenerator()
qa_pairs = generator.generate_dataset(chunks, target_size=50)
generator.save_dataset(qa_pairs)
```

### 1.2 Métriques RAGAS

Le module `eval/metrics.py` implémente des métriques inspirées de RAGAS :

| Métrique | Description | Plage |
|----------|-------------|-------|
| **Retrieval Accuracy** | Le bon document est-il dans le top-k ? | 0-100% |
| **MRR** (Mean Reciprocal Rank) | Rang moyen du bon document | 0-1 |
| **Faithfulness** | La réponse est-elle fidèle aux sources ? | 0-1 |
| **Answer Relevance** | La réponse répond-elle à la question ? | 0-1 |

### 1.3 Benchmark Runner

Le module `eval/benchmark.py` permet de comparer différentes configurations :

```python
from eval.benchmark import BenchmarkRunner, BenchmarkConfig

runner = BenchmarkRunner()

# Définir une configuration
config = BenchmarkConfig(
    name="full_pipeline",
    use_query_rewriting=True,
    use_reranking=True,
    use_hybrid=True,
    use_context_expansion=True,
    top_k=5
)

# Lancer le benchmark
report = runner.run_benchmark(qa_pairs, config)
print(report.summary())
```

### 1.4 CLI d'évaluation

```bash
# Générer un dataset de 50 paires QA
python -m eval.run_eval --generate 50

# Lancer un benchmark
python -m eval.run_eval --benchmark

# Comparer les configurations (full, no_reranking, no_hybrid, minimal)
python -m eval.run_eval --compare
```

#### Exemple de sortie

```
=== Benchmark Report: full ===
Total questions: 50

Retrieval Metrics:
  Accuracy (Hit@k): 82.0%
  MRR: 0.756
  Avg Rank: 1.45

Generation Metrics:
  Faithfulness: 87.5%
  Relevance: 91.2%
```

---

## 2. Robustesse et Confiance

### 2.1 Seuil de confiance

Le système refuse de répondre si le score de confiance est trop bas.

#### Configuration

```python
# Dans rag_pipeline/config.py
confidence_threshold: float = 0.25  # Score minimum requis
```

#### Comportement

- Si `max_score < confidence_threshold` : retourne un message de refus
- Le flag `low_confidence` est ajouté au contexte de retrieval
- L'interface web affiche un badge d'avertissement

### 2.2 Prompt anti-hallucination

Le prompt système a été renforcé avec des règles strictes :

```
RÈGLES STRICTES DE VÉRACITÉ :

1. VÉRACITÉ ABSOLUE - Réponds UNIQUEMENT à partir des documents fournis
2. Formules de refus obligatoires :
   - "Je n'ai pas trouvé cette information..."
   - "Les documents fournis ne contiennent pas..."
3. Citation des sources avec numéro et date
4. Protection des données personnelles
5. Questions hors-sujet : refus poli
```

### 2.3 Filtrage PII

Le module `rag_pipeline/pii_filter.py` détecte et masque les informations personnelles.

#### Types de PII détectés

| Type | Pattern | Masque |
|------|---------|--------|
| Téléphone FR | `06 12 34 56 78`, `+33...` | `[TELEPHONE MASQUE]` |
| Email | `user@domain.com` | `[EMAIL MASQUE]` |
| IBAN | `FR76 3000 6000...` | `[IBAN MASQUE]` |
| Carte bancaire | `4111 1111 1111 1111` | `[CARTE MASQUEE]` |
| Adresse | `12 rue de Paris, 75001` | `[ADRESSE MASQUEE]` |
| N° Sécu (FR) | `1 85 12 75 115...` | `[NSS MASQUE]` |

#### Utilisation

```python
from rag_pipeline.pii_filter import PIIFilter

filter = PIIFilter()

# Détecter les PII
matches = filter.detect(text)

# Masquer les PII
masked_text, matches = filter.mask(text)

# Vérifier la présence de PII
has_pii = filter.has_pii(text)
```

#### Activation

```python
# Dans rag_pipeline/config.py
enable_pii_filter: bool = True
```

---

## 3. Mises à jour Incrémentales

### 3.1 Delta Tracker

Le module `rag_pipeline/delta_tracker.py` suit les modifications de fichiers.

#### Fonctionnement

1. **Hash SHA256** de chaque fichier indexé
2. **Détection des changements** :
   - Nouveaux fichiers (non trackés)
   - Fichiers modifiés (hash différent)
   - Fichiers supprimés (trackés mais absents)

#### État persistant

L'état est sauvegardé dans `rag_data/file_state.json` :

```json
{
  "last_updated": "2024-01-15T10:30:00",
  "total_files": 42,
  "files": {
    "/path/to/conversation.txt": {
      "content_hash": "abc123...",
      "last_modified": "2024-01-15T09:00:00",
      "last_indexed": "2024-01-15T10:00:00",
      "chunk_ids": ["conv_chunk_000", "conv_chunk_001"],
      "file_size": 15234
    }
  }
}
```

### 3.2 Vector Store incrémental

Nouvelles méthodes dans `rag_pipeline/vector_store.py` :

```python
# Ajouter des vecteurs
vector_store.add_vectors(new_chunks, new_embeddings)

# Supprimer des vecteurs par chunk_id
vector_store.remove_vectors(["chunk_001", "chunk_002"])

# Mise à jour combinée (suppression + ajout)
removed, added = vector_store.update_vectors(
    chunk_ids_to_remove=["old_chunk"],
    new_chunks=[new_chunk],
    new_embeddings=embeddings
)
```

### 3.3 Script de mise à jour

```bash
# Afficher le statut (changements détectés)
python update_index.py --status

# Lancer une mise à jour incrémentale
python update_index.py

# Forcer une reconstruction complète
python update_index.py --full
```

#### Exemple de sortie

```
============================================================
Incremental Index Update
============================================================

Changes detected: New: 2, Modified: 1, Deleted: 0

Loading components...
Removing 15 old chunks...

Processing 3 files...
  [1/3] new_conversation.txt
  [2/3] updated_conversation.txt
  [3/3] another_new.txt

Enriching 45 chunks...

Generating embeddings for 45 chunks...
  [45/45] Done

Saving vector store...
Rebuilding BM25 index...
Rebuilding metadata index...
Saving tracker state...

============================================================
Update Complete
============================================================
Total chunks in index: 1250
Tracked files: 44
```

---

## 4. Expérience Utilisateur

### 4.1 Citations interactives

Les sources sont maintenant cliquables et affichent un modal avec le contenu complet.

#### API Endpoint

```
GET /api/chunks/{chunk_id}
```

**Réponse** :
```json
{
  "chunk_id": "conv_chunk_001",
  "content": "...",
  "summary": "...",
  "participants": ["Alice", "Bob"],
  "date_start": "2024-01-15 10:00:00",
  "date_end": "2024-01-15 12:30:00",
  "file_source": "conversation_alice.txt",
  "message_count": 45,
  "hypothetical_questions": [
    "Quand Alice et Bob ont-ils parlé de X ?",
    "..."
  ]
}
```

#### Interface

- Clic sur une source → Modal avec contenu complet
- Affichage du résumé, métadonnées, questions hypothétiques
- Contenu brut de la conversation

### 4.2 Questions de suivi

Le système génère automatiquement 3 questions de suivi après chaque réponse.

#### Événement SSE

```json
{"type": "followups", "questions": [
  "Avez-vous d'autres conversations sur ce sujet ?",
  "Quand avez-vous reparlé de X ?",
  "Qui d'autre a participé à cette discussion ?"
]}
```

#### Interface

- Boutons cliquables sous la réponse
- Clic → Remplit le champ et envoie automatiquement

### 4.3 Indicateurs de progression

Le streaming inclut maintenant des événements de progression :

| Étape | Message |
|-------|---------|
| `search` | "Recherche en cours..." |
| `documents` | "Lecture de N documents..." |
| `generating` | "Génération de la réponse..." |
| `followups` | "Préparation des suggestions..." |

#### Événement SSE

```json
{"type": "progress", "step": "documents", "message": "Lecture de 5 documents...", "count": 5}
```

### 4.4 Gestion de la faible confiance

Quand le score de confiance est trop bas :

1. Pas d'appel au LLM
2. Message immédiat : "Je n'ai pas trouvé d'information pertinente..."
3. Badge `low_confidence` dans les métadonnées de la réponse

---

## Architecture des fichiers

```
instagram-assistant/
├── eval/
│   ├── __init__.py
│   ├── synthetic_generator.py   # Génération QA
│   ├── metrics.py               # Métriques RAGAS
│   ├── benchmark.py             # Runner de benchmark
│   └── run_eval.py              # CLI
├── rag_pipeline/
│   ├── config.py                # + confidence_threshold, enable_pii_filter
│   ├── advanced_retriever.py    # + low_confidence, max_confidence_score
│   ├── chat.py                  # + followup, PII filter
│   ├── vector_store.py          # + add/remove/update vectors
│   ├── pii_filter.py            # NEW: Filtrage PII
│   └── delta_tracker.py         # NEW: Suivi des fichiers
├── web/
│   ├── index.html               # + Modal source
│   └── static/
│       ├── app.js               # + Progress, followups, modal
│       └── style.css            # + Styles nouveaux composants
├── update_index.py              # NEW: Script mise à jour incrémentale
└── docs/
    └── FEATURES.md              # Cette documentation
```

---

## Dépendances

Aucune nouvelle dépendance n'est requise. Les fonctionnalités utilisent :
- `hashlib` (stdlib) pour le hashing
- `re` (stdlib) pour les regex PII
- Les modèles Ollama existants pour la génération

---

## FAQ

### Q: Comment désactiver le filtrage PII ?

```python
# Dans config.py ou à l'instanciation
config.enable_pii_filter = False
```

### Q: Comment ajuster le seuil de confiance ?

```python
# Plus strict (refuse plus souvent)
config.confidence_threshold = 0.4

# Plus permissif
config.confidence_threshold = 0.15
```

### Q: La mise à jour incrémentale ne détecte pas mes changements ?

Vérifiez que :
1. Les fichiers sont dans `instagram_conversations/`
2. L'extension est `.txt`
3. Le contenu a réellement changé (pas juste la date)

### Q: Comment forcer une reconstruction complète ?

```bash
python update_index.py --full
```

Ou supprimez `rag_data/file_state.json` puis relancez `update_index.py`.
