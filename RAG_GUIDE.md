# Guide complet - RAG Local pour Conversations Instagram

Ce document décrit pas à pas comment mettre en place un pipeline RAG fiable, contrôlé et auditable, optimisé pour des conversations longues et non structurées (DM Instagram, chats, messages).

---

## Objectifs

- Améliorer drastiquement la précision du retrieval
- Éviter les réponses vagues ou hallucinées
- Produire des réponses factuelles, sourcées et vérifiables
- Garder un système local, maîtrisé et débogable

---

## Architecture cible

```
Documents bruts (DM)
        |
Nettoyage & structuration
        |
Chunking sémantique (conversationnel)
        |
Embeddings de qualité (BGE-M3)
        |
Vector Store (FAISS)
        |
Retrieval contrôlé (Top-K + Reranking)
        |
LLM discipliné + prompt strict
```

---

## 1. Choix des outils (fondation critique)

### A éviter

- RAG intégré d'Open WebUI (POC uniquement)
- Chunking automatique par nombre de tokens
- Embeddings génériques ou non multilingues

### Recommandé

**Vector Store**
- FAISS -> rapide, simple, 100% local
- Chroma -> persistance + métadonnées riches (si besoin de filtrage natif)

**Embeddings (OBLIGATOIRES)**
- `BAAI/bge-m3` (meilleur choix multilingue FR/EN, 1024 dim)
- `intfloat/e5-large-v2` (alternative)

> Les embeddings représentent la majorité de la qualité du RAG.

---

## 2. Préparation des données

### Nettoyage minimal

- Supprimer les messages vides ou non textuels
- Normaliser les dates
- Conserver systématiquement :
  - auteur
  - timestamp
  - contenu textuel brut

### Format de travail recommandé

```json
{
  "conversation_id": "pauline_2023_01",
  "timestamp": "2023-01-12 18:42",
  "author": "Pauline",
  "content": "Je peux pas ce soir, trop crevée"
}
```

---

## 3. Chunking adapté aux conversations

### Mauvaises pratiques

- Chunk par taille fixe (ex : 512 tokens)
- Chunk par message unique
- Chunk sans continuité temporelle

### Bon chunking

| Option | Description | Quand l'utiliser |
|--------|-------------|------------------|
| **A - Conversation complète** | 1 chunk = 1 conversation | Si < 3-5k tokens |
| **B - Période logique** (recommandé) | 30-80 messages, max 3 jours | Cas général |
| **C - Arc narratif** | Découpe sur pause longue ou changement de sujet | Conversations très longues |

### Configuration actuelle (Option B)

```python
chunk_max_messages: int = 50    # Split si >50 messages
chunk_max_days: int = 3         # Split si >3 jours (PRIORITAIRE)
chunk_overlap: int = 5          # Chevauchement entre chunks
```

**Résultat** : 43,675 chunks pour 562,168 messages (~12.9 msg/chunk en moyenne)

### Astuce clé (très importante)

Ajouter un résumé court en tête de chaque chunk :

```
Résumé du chunk :
Conversation entre X et Y.
Période: 30/05/2024 - 02/06/2024.
49 messages échangés.
Sujets abordés: video, instagram, shoot.
Contient 4 média(s).
```

> Le retrieval matche souvent le résumé, pas le texte brut.

---

## 4. Métadonnées à indexer

Toujours inclure :
- `conversation_id`
- `participants`
- `date_start`
- `date_end`
- `message_count`
- `summary`

Ces métadonnées permettent :
- le filtrage
- l'audit des réponses
- le débogage du retrieval

---

## 5. Indexation

### Paramètres recommandés

- Distance : cosine (Inner Product sur vecteurs normalisés)
- Normalisation : activée (L2)
- Vector = embedding(summary + contenu_du_chunk)

### Script d'indexation avec reprise

```bash
# Lancer/reprendre l'indexation
python3 setup_rag_batch.py

# Voir l'état actuel
python3 setup_rag_batch.py --status

# Recommencer de zéro
python3 setup_rag_batch.py --reset
```

Le script sauvegarde un checkpoint après chaque batch de 500 chunks. Si le script s'arrête, il reprend automatiquement.

---

## 6. Retrieval (point de rupture classique)

### Réglages de base

```python
top_k: int = 5              # Nombre de chunks retournés
min_similarity: float = 0.3  # Score minimum (cosine)
```

### Problème avec les conversations longues (10k+ messages)

Une conversation de 10k messages = ~200 chunks. Si l'information est dispersée, 5 chunks ne suffisent pas.

### Améliorations recommandées

#### 1. Reranker Cross-Encoder

```python
# Récupérer plus de candidats, puis reranker
initial_k = 20
top_k = 5

# Retrieval initial (dense search)
candidates = vector_store.search(query_embedding, top_k=initial_k)

# Reranking avec cross-encoder
from sentence_transformers import CrossEncoder
reranker = CrossEncoder('BAAI/bge-reranker-base')

pairs = [(query, c.chunk.content) for c in candidates]
scores = reranker.predict(pairs)

# Garder les top_k meilleurs après reranking
reranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)[:top_k]
```

#### 2. Context Expansion (chunks adjacents)

Quand un chunk pertinent est trouvé, récupérer aussi chunk-1 et chunk+1 :

```python
def expand_context(chunk_id: str, all_chunks: List[Chunk]) -> List[Chunk]:
    # Parse chunk_id: "conv_123_chunk_005"
    parts = chunk_id.rsplit("_chunk_", 1)
    conv_id = parts[0]
    chunk_num = int(parts[1])

    # Récupérer les chunks adjacents de la même conversation
    adjacent = []
    for offset in [-1, 0, 1]:
        target_id = f"{conv_id}_chunk_{chunk_num + offset:03d}"
        match = next((c for c in all_chunks if c.chunk_id == target_id), None)
        if match:
            adjacent.append(match)

    return adjacent
```

#### 3. Hybrid Search (BM25 + Dense)

Combiner recherche par mots-clés exacts et recherche sémantique :

```python
from rank_bm25 import BM25Okapi

# Index BM25
tokenized_chunks = [chunk.content.lower().split() for chunk in chunks]
bm25 = BM25Okapi(tokenized_chunks)

def hybrid_search(query: str, alpha: float = 0.5):
    # Dense search
    dense_scores = vector_store.search(query_embedding, top_k=50)

    # BM25 search
    bm25_scores = bm25.get_scores(query.lower().split())

    # Normaliser et combiner
    final_scores = alpha * dense_scores + (1 - alpha) * bm25_scores

    return top_k_by_score(final_scores)
```

### Règle d'or

> Peu de documents très pertinents > beaucoup de documents vagues.

---

## 7. Modèle LLM (small mais discipliné)

### Choix recommandés

1. Llama 3.1 8B Instruct
2. Qwen 2.5 7B Instruct
3. Mistral 7B Instruct

### Réglages conseillés

```python
temperature: float = 0.1    # Bas = plus factuel
top_p: float = 0.9          # Nucleus sampling
max_tokens: int = 1024      # Limite la sortie
```

---

## 8. Prompt système (obligatoire)

Le LLM doit être forcé à utiliser le contexte RAG.

```
Tu es un assistant qui répond aux questions sur des conversations Instagram.

RÈGLES CRITIQUES :
1. Réponds UNIQUEMENT à partir des documents fournis
2. Si l'information n'est pas dans les documents, dis "Je n'ai pas trouvé cette information dans les conversations."
3. Cite TOUJOURS tes sources (numéro du document, date, participants)
4. Sois concis et factuel
5. Si l'information est partielle, explique ce qui manque
6. Respecte la vie privée (ces conversations sont personnelles)
```

> Sans prompt strict, même un bon RAG échoue.

---

## 9. Tests & validation

### Tests à effectuer

| Type | Ce qu'on teste |
|------|----------------|
| **Question avec réponse connue** | Exactitude du retrieval + LLM |
| **Question sans réponse** | Refus correct ("je n'ai pas trouvé...") |
| **Question ambiguë** | Signalement d'ambiguïté |
| **Question temporelle** | "Quand avons-nous parlé de X ?" |
| **Question multi-personne** | "Qui a mentionné X ?" |

### Indicateurs d'échec

- Réponses générales (non sourcées)
- Ton affirmatif sans citations
- Hallucinations (informations inventées)
- Réponse hors-sujet

---

## 10. Démarrage rapide

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Indexer les conversations (avec reprise automatique)
python3 setup_rag_batch.py

# 3. Lancer le chat
python3 chat_instagram.py
```

### Commandes utiles dans le chat

```
/sources     - Affiche les sources du dernier message
/clear       - Efface l'historique de conversation
/quit        - Quitter
```

---

## Résumé des fichiers

| Fichier | Rôle |
|---------|------|
| `rag_pipeline/config.py` | Configuration centralisée |
| `rag_pipeline/chunker.py` | Découpage des conversations |
| `rag_pipeline/embeddings.py` | Modèle BGE-M3 |
| `rag_pipeline/vector_store.py` | Index FAISS |
| `rag_pipeline/retriever.py` | Recherche + formatage contexte |
| `rag_pipeline/chat.py` | Interface avec Ollama |
| `setup_rag_batch.py` | Indexation avec checkpoints |
| `chat_instagram.py` | Interface CLI |

---

## Rappel clé

> Si le RAG échoue, ne change pas le modèle en premier.
> Change le chunking ou les embeddings.

Le pipeline est la pièce centrale, pas le LLM.

---

## Améliorations implémentées

- [x] Reranker cross-encoder (BGE-reranker-base)
- [x] Context expansion (chunks adjacents)
- [x] Hybrid search (BM25 + dense)
- [x] Pre-filtering par métadonnées (SQLite)

## Améliorations futures

- [ ] Index FAISS optimisé (IVFFlat ou HNSW) si >100k chunks
- [ ] Query expansion (reformulation automatique)
- [ ] Feedback loop (apprentissage des bonnes réponses)
