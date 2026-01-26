# Instagram Assistant - API Reference

Documentation de l'API REST du serveur FastAPI.

---

## Base URL

```
http://localhost:8000
```

---

## Endpoints

### Status

#### `GET /api/status`

Retourne l'état du système.

**Réponse** :
```json
{
  "ready": true,
  "chunks_count": 1250,
  "has_bm25": true,
  "has_reranker": true,
  "has_metadata": true
}
```

---

### Conversations

#### `GET /api/conversations`

Liste toutes les conversations.

**Réponse** :
```json
[
  {
    "id": "abc123",
    "title": "Discussion sur le projet",
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T11:45:00",
    "message_count": 4
  }
]
```

#### `POST /api/conversations`

Crée une nouvelle conversation.

**Body** :
```json
{
  "title": "Ma nouvelle conversation"  // optionnel
}
```

**Réponse** :
```json
{
  "id": "def456",
  "title": "Ma nouvelle conversation",
  "created_at": "2024-01-15T12:00:00",
  "updated_at": "2024-01-15T12:00:00",
  "messages": []
}
```

#### `GET /api/conversations/{conv_id}`

Récupère une conversation avec tous ses messages.

**Réponse** :
```json
{
  "id": "abc123",
  "title": "Discussion sur le projet",
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T11:45:00",
  "messages": [
    {
      "role": "user",
      "content": "Quand ai-je parlé de vacances ?",
      "timestamp": "2024-01-15T10:30:00"
    },
    {
      "role": "assistant",
      "content": "D'après les conversations...",
      "timestamp": "2024-01-15T10:30:15",
      "sources": [...],
      "low_confidence": false,
      "confidence_score": 0.756
    }
  ]
}
```

#### `DELETE /api/conversations/{conv_id}`

Supprime une conversation.

**Réponse** :
```json
{
  "status": "deleted"
}
```

#### `PATCH /api/conversations/{conv_id}`

Met à jour le titre d'une conversation.

**Body** :
```json
{
  "title": "Nouveau titre"
}
```

---

### Participants

#### `GET /api/participants`

Liste tous les participants pour le filtrage.

**Réponse** :
```json
[
  {"name": "Alice", "count": 150},
  {"name": "Bob", "count": 89},
  {"name": "Charlie", "count": 45}
]
```

---

### Chunks

#### `GET /api/chunks/{chunk_id}`

Récupère le contenu complet d'un chunk (pour le modal de détail).

**Réponse** :
```json
{
  "chunk_id": "conversation_alice_chunk_005",
  "content": "[2024-01-15 10:00] Alice: Salut !\n[2024-01-15 10:01] Bob: Hey !...",
  "summary": "Discussion entre Alice et Bob sur le projet X. Période: 15/01/2024. 45 messages échangés.",
  "participants": ["Alice", "Bob"],
  "date_start": "2024-01-15 10:00:00",
  "date_end": "2024-01-15 12:30:00",
  "file_source": "conversation_alice.txt",
  "message_count": 45,
  "hypothetical_questions": [
    "Quand Alice et Bob ont-ils parlé du projet X ?",
    "Qu'ont décidé Alice et Bob concernant la deadline ?",
    "Quel était le sujet principal de cette discussion ?"
  ]
}
```

---

### Chat

#### `POST /api/chat`

Envoie un message et reçoit une réponse (non-streaming).

**Body** :
```json
{
  "message": "Quand ai-je parlé de vacances avec Marie ?",
  "conversation_id": "abc123",  // optionnel, crée une nouvelle conv si absent
  "participant_filter": "Marie",  // optionnel
  "year_filter": 2023,  // optionnel
  "date_start": "2023-01-01",  // optionnel
  "date_end": "2023-12-31",  // optionnel
  "use_reranking": true,
  "use_hybrid": true,
  "expand_context": true
}
```

**Réponse** :
```json
{
  "conversation_id": "abc123",
  "message": {
    "role": "assistant",
    "content": "D'après les conversations avec Marie...",
    "timestamp": "2024-01-15T10:30:15",
    "sources": [...]
  },
  "sources": [
    {
      "rank": 1,
      "chunk_id": "conv_marie_chunk_012",
      "file": "conversation_marie.txt",
      "participants": ["Ismaël", "Marie"],
      "date_start": "2023-07-15",
      "date_end": "2023-07-15",
      "score": 0.85,
      "expanded": false,
      "preview": "Discussion sur les vacances d'été..."
    }
  ]
}
```

#### `POST /api/chat/stream`

Envoie un message et reçoit une réponse en streaming (SSE).

**Body** : Identique à `/api/chat`

**Réponse** : Server-Sent Events (SSE)

```
Content-Type: text/event-stream

data: {"type": "conversation_id", "id": "abc123"}

data: {"type": "progress", "step": "search", "message": "Recherche en cours..."}

data: {"type": "progress", "step": "documents", "message": "Lecture de 5 documents...", "count": 5}

data: {"type": "sources", "sources": [...]}

data: {"type": "progress", "step": "generating", "message": "Génération de la réponse..."}

data: {"type": "chunk", "content": "D'après "}
data: {"type": "chunk", "content": "les conversations "}
data: {"type": "chunk", "content": "avec Marie..."}

data: {"type": "progress", "step": "followups", "message": "Préparation des suggestions..."}

data: {"type": "followups", "questions": ["Avez-vous d'autres discussions avec Marie ?", "Quand êtes-vous partis en vacances ?", "Qui d'autre était présent ?"]}

data: {"type": "done"}
```

---

## Types d'événements SSE

| Type | Description | Données |
|------|-------------|---------|
| `conversation_id` | ID de la conversation | `{id: string}` |
| `progress` | Étape de traitement | `{step: string, message: string, count?: number}` |
| `sources` | Sources trouvées | `{sources: Source[]}` |
| `chunk` | Token de réponse | `{content: string}` |
| `followups` | Questions de suivi | `{questions: string[]}` |
| `done` | Fin du stream | `{}` |
| `error` | Erreur | `{message: string}` |

### Étapes de progression

| Step | Description |
|------|-------------|
| `search` | Recherche dans l'index |
| `documents` | Lecture des documents |
| `generating` | Génération de la réponse |
| `followups` | Génération des suggestions |

---

## Modèles de données

### Source

```typescript
interface Source {
  rank: number;           // Position dans les résultats (1-indexed)
  chunk_id: string;       // ID unique du chunk
  file: string;           // Nom du fichier source
  participants: string[]; // Liste des participants
  date_start: string;     // Date de début (YYYY-MM-DD)
  date_end: string;       // Date de fin (YYYY-MM-DD)
  score: number;          // Score de pertinence (0-1)
  expanded: boolean;      // True si ajouté par context expansion
  preview: string;        // Aperçu du contenu (200 chars max)
}
```

### Message

```typescript
interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;       // ISO 8601
  sources?: Source[];      // Seulement pour assistant
  low_confidence?: boolean;
  confidence_score?: number;
}
```

### Conversation

```typescript
interface Conversation {
  id: string;
  title: string;
  created_at: string;      // ISO 8601
  updated_at: string;      // ISO 8601
  messages: Message[];
}
```

---

## Codes d'erreur

| Code | Description |
|------|-------------|
| 400 | Requête invalide |
| 404 | Ressource non trouvée |
| 503 | RAG non initialisé (index manquant) |

**Format d'erreur** :
```json
{
  "detail": "Description de l'erreur"
}
```

---

## Exemples cURL

### Vérifier le statut

```bash
curl http://localhost:8000/api/status
```

### Envoyer un message

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "De quoi ai-je parlé hier ?"}'
```

### Streaming avec filtres

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Résume mes conversations avec Alice",
    "participant_filter": "Alice",
    "year_filter": 2023
  }'
```

### Récupérer un chunk

```bash
curl http://localhost:8000/api/chunks/conversation_alice_chunk_005
```
