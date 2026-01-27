# Instagram Assistant - API Reference

FastAPI REST API documentation.

---

## Base URL

```
http://localhost:8000
```

---

## Endpoints

### Status

#### `GET /api/status`

Returns system status.

**Response**:
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

List all conversations.

**Response**:
```json
[
  {
    "id": "abc123",
    "title": "Project Discussion",
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T11:45:00",
    "message_count": 4
  }
]
```

#### `POST /api/conversations`

Create a new conversation.

**Body**:
```json
{
  "title": "My new conversation"  // optional
}
```

**Response**:
```json
{
  "id": "def456",
  "title": "My new conversation",
  "created_at": "2024-01-15T12:00:00",
  "updated_at": "2024-01-15T12:00:00",
  "messages": []
}
```

#### `GET /api/conversations/{conv_id}`

Retrieve a conversation with all messages.

**Response**:
```json
{
  "id": "abc123",
  "title": "Project Discussion",
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T11:45:00",
  "messages": [
    {
      "role": "user",
      "content": "When did I talk about vacation?",
      "timestamp": "2024-01-15T10:30:00"
    },
    {
      "role": "assistant",
      "content": "According to the conversations...",
      "timestamp": "2024-01-15T10:30:15",
      "sources": [...],
      "low_confidence": false,
      "confidence_score": 0.756
    }
  ]
}
```

#### `DELETE /api/conversations/{conv_id}`

Delete a conversation.

**Response**:
```json
{
  "status": "deleted"
}
```

#### `PATCH /api/conversations/{conv_id}`

Update conversation title.

**Body**:
```json
{
  "title": "New title"
}
```

---

### Participants

#### `GET /api/participants`

List all participants for filtering.

**Response**:
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

Retrieve full chunk content (for detail modal).

**Response**:
```json
{
  "chunk_id": "conversation_alice_chunk_005",
  "content": "[2024-01-15 10:00] Alice: Hi!\n[2024-01-15 10:01] Bob: Hey!...",
  "summary": "Discussion between Alice and Bob about project X. Period: 01/15/2024. 45 messages exchanged.",
  "narrative_summary": "Alice and Bob finalize project X deadline with mutual agreement.",
  "participants": ["Alice", "Bob"],
  "date_start": "2024-01-15 10:00:00",
  "date_end": "2024-01-15 12:30:00",
  "file_source": "conversation_alice.txt",
  "message_count": 45,
  "hypothetical_questions": [
    "When did Alice and Bob discuss project X?",
    "What did Alice and Bob decide about the deadline?",
    "What was the main topic of this discussion?"
  ],
  "speaker_intents": {
    "Alice": "seeking deadline confirmation",
    "Bob": "proposing timeline and getting approval"
  },
  "temporal_context": "during project X planning phase",
  "emotions": {
    "dominant": "focus",
    "tone": "professional",
    "tension_level": "low"
  }
}
```

---

### Chat

#### `POST /api/chat`

Send a message and receive a response (non-streaming).

**Body**:
```json
{
  "message": "When did I talk about vacation with Marie?",
  "conversation_id": "abc123",  // optional, creates new conv if absent
  "participant_filter": "Marie",  // optional
  "year_filter": 2023,  // optional
  "date_start": "2023-01-01",  // optional
  "date_end": "2023-12-31",  // optional
  "use_reranking": true,
  "use_hybrid": true,
  "expand_context": true
}
```

**Response**:
```json
{
  "conversation_id": "abc123",
  "message": {
    "role": "assistant",
    "content": "According to conversations with Marie...",
    "timestamp": "2024-01-15T10:30:15",
    "sources": [...]
  },
  "sources": [
    {
      "rank": 1,
      "chunk_id": "conv_marie_chunk_012",
      "file": "conversation_marie.txt",
      "participants": ["User", "Marie"],
      "date_start": "2023-07-15",
      "date_end": "2023-07-15",
      "score": 0.85,
      "expanded": false,
      "preview": "Discussion about summer vacation..."
    }
  ]
}
```

#### `POST /api/chat/stream`

Send a message and receive a streaming response (SSE).

**Body**: Same as `/api/chat`

**Response**: Server-Sent Events (SSE)

```
Content-Type: text/event-stream

data: {"type": "conversation_id", "id": "abc123"}

data: {"type": "progress", "step": "search", "message": "Searching..."}

data: {"type": "progress", "step": "documents", "message": "Reading 5 documents...", "count": 5}

data: {"type": "sources", "sources": [...]}

data: {"type": "progress", "step": "generating", "message": "Generating response..."}

data: {"type": "chunk", "content": "According "}
data: {"type": "chunk", "content": "to conversations "}
data: {"type": "chunk", "content": "with Marie..."}

data: {"type": "progress", "step": "followups", "message": "Preparing suggestions..."}

data: {"type": "followups", "questions": ["Do you have other discussions with Marie?", "When did you go on vacation?", "Who else was present?"]}

data: {"type": "done"}
```

---

## SSE Event Types

| Type | Description | Data |
|------|-------------|------|
| `conversation_id` | Conversation ID | `{id: string}` |
| `progress` | Processing step | `{step: string, message: string, count?: number}` |
| `sources` | Found sources | `{sources: Source[]}` |
| `chunk` | Response token | `{content: string}` |
| `followups` | Follow-up questions | `{questions: string[]}` |
| `done` | Stream end | `{}` |
| `error` | Error | `{message: string}` |

### Progress Steps

| Step | Description |
|------|-------------|
| `search` | Searching index |
| `documents` | Reading documents |
| `generating` | Generating response |
| `followups` | Generating suggestions |

---

## Data Models

### Source

```typescript
interface Source {
  rank: number;           // Position in results (1-indexed)
  chunk_id: string;       // Unique chunk ID
  file: string;           // Source file name
  participants: string[]; // Participant list
  date_start: string;     // Start date (YYYY-MM-DD)
  date_end: string;       // End date (YYYY-MM-DD)
  score: number;          // Relevance score (0-1)
  expanded: boolean;      // True if added by context expansion
  preview: string;        // Content preview (max 200 chars)
}
```

### Message

```typescript
interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;       // ISO 8601
  sources?: Source[];      // Only for assistant
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

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Invalid request |
| 404 | Resource not found |
| 503 | RAG not initialized (missing index) |

**Error format**:
```json
{
  "detail": "Error description"
}
```

---

## cURL Examples

### Check status

```bash
curl http://localhost:8000/api/status
```

### Send a message

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What did I discuss yesterday?"}'
```

### Streaming with filters

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Summarize my conversations with Alice",
    "participant_filter": "Alice",
    "year_filter": 2023
  }'
```

### Retrieve a chunk

```bash
curl http://localhost:8000/api/chunks/conversation_alice_chunk_005
```
