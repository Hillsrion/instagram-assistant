# Backend Review and Fixes - Instagram Assistant

**Date:** 2026-01-26
**Overall Assessment:** 7.5/10 - Strong foundation with important gaps to address before production deployment

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Critical Issues](#critical-issues)
4. [High Priority Issues](#high-priority-issues)
5. [Medium Priority Issues](#medium-priority-issues)
6. [Detailed Fix Implementations](#detailed-fix-implementations)
7. [Security Concerns](#security-concerns)
8. [Performance Optimizations](#performance-optimizations)
9. [Testing Recommendations](#testing-recommendations)
10. [Deployment Checklist](#deployment-checklist)

---

## Executive Summary

The Instagram Assistant is a well-architected RAG (Retrieval-Augmented Generation) system with a FastAPI backend serving an advanced question-answering system over Instagram conversations. The codebase demonstrates solid engineering practices with modular design, comprehensive RAG pipeline components, and thoughtful data processing.

### Key Strengths
- ✅ Modular RAG pipeline design
- ✅ Hybrid search (dense + BM25)
- ✅ Cross-encoder reranking
- ✅ Context expansion with adjacent chunks
- ✅ Metadata filtering capabilities
- ✅ Type hints throughout codebase
- ✅ Streaming API support
- ✅ Lazy loading for expensive resources

### Critical Gaps
- ❌ ChatBot constructor mismatch will crash on startup
- ❌ Hardcoded paths prevent portability
- ❌ Global mutable state not thread-safe
- ❌ Security vulnerabilities (pickle, no input validation)
- ❌ O(n) lookups causing performance issues
- ❌ Race conditions on file I/O

**Estimated effort to production-ready:** 2-3 weeks for a single developer

---

## Architecture Overview

### Project Structure
```
instagram-assistant/
├── app.py                          # FastAPI application (main entry point)
├── requirements.txt                # Dependencies
├── setup_rag_batch.py             # RAG indexing pipeline
├── rag_pipeline/                   # Core RAG components
│   ├── config.py                   # Centralized configuration
│   ├── chunker.py                  # Semantic chunking
│   ├── embeddings.py               # Embedding models (BGE-M3)
│   ├── vector_store.py             # FAISS vector store
│   ├── bm25_index.py               # Lexical search index
│   ├── metadata_store.py           # SQLite metadata for filtering
│   ├── retriever.py                # Basic retriever
│   ├── advanced_retriever.py       # Advanced retriever with reranking
│   ├── reranker.py                 # Cross-encoder reranking
│   └── chat.py                     # Ollama-based chat interface
├── web/                            # Frontend
├── instagram_conversations/        # Raw conversation data
└── rag_data/                       # Processed data & indexes
```

### Architecture Patterns Used
- **Factory Pattern**: `create_advanced_retriever()` for dependency injection
- **Dataclass Pattern**: Used for data models (Chunk, Message, SearchResult)
- **Lazy Loading**: Models loaded on first use
- **Streaming**: SSE-based streaming for chat responses
- **Lifespan Context Manager**: Resource initialization/cleanup in FastAPI

---

## Critical Issues

### Issue #1: ChatBot Constructor Mismatch - WILL CRASH ON STARTUP

**Location:** `rag_pipeline/chat.py:54`, `app.py:149`

**Problem:**
```python
# chat.py defines constructor expecting 2 parameters
def __init__(self, retriever: Retriever, config: Config = None):
    self.retriever = retriever
    # ...

# But app.py calls it with only 1 parameter
chatbot = ChatBot(config)  # MISSING retriever!
```

**Impact:** Application will crash immediately on startup with `TypeError`

**Fix:**
```python
# app.py, lines 143-149
@asynccontextmanager
async def lifespan(app: FastAPI):
    config = Config()
    retriever, components = create_advanced_retriever(config, ...)

    # FIX: Pass retriever as first argument
    chatbot = ChatBot(retriever, config)

    # Store in app state (not globals)
    app.state.retriever = retriever
    app.state.chatbot = chatbot
    app.state.components = components
```

---

### Issue #2: Hardcoded Paths - Not Portable

**Location:** `rag_pipeline/config.py:13-14`

**Problem:**
```python
@dataclass
class Config:
    base_dir: Path = Path("/Users/ismaelsebbane/dev/lab/instagram-assistant")
    user_name: str = "Ismaël"  # Also hardcoded
```

**Impact:** Code won't run on other machines or in Docker containers

**Fix:**
```python
import os
from dataclasses import dataclass, field

@dataclass
class Config:
    # Use relative path from this file's location
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    # Load from environment variables
    user_name: str = field(default_factory=lambda: os.getenv("USER_NAME", "User"))

    def __post_init__(self):
        # Allow environment override
        if env_base := os.getenv("INSTAGRAM_ASSISTANT_HOME"):
            self.base_dir = Path(env_base)

        # Ensure directories exist
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)
```

**Create .env file:**
```bash
# .env
USER_NAME=Ismaël
INSTAGRAM_ASSISTANT_HOME=/path/to/app
OLLAMA_URL=http://localhost:11434
```

---

### Issue #3: Global Mutable State - Not Thread-Safe

**Location:** `app.py:114-117`

**Problem:**
```python
# Global variables - not thread-safe
retriever = None
chatbot = None
config = None
components = None
```

**Impact:**
- Won't work with multiple Gunicorn workers
- Makes testing difficult
- Race conditions possible

**Fix:**
```python
# Remove global variables entirely

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize RAG components on startup."""
    try:
        config = Config()
        retriever, components = create_advanced_retriever(config, ...)
        chatbot = ChatBot(retriever, config)

        # Store in app.state instead of globals
        app.state.retriever = retriever
        app.state.chatbot = chatbot
        app.state.components = components
        app.state.config = config

        logger.info(f"✅ RAG initialized with {components['vector_store'].size} chunks")
    except Exception as e:
        logger.critical(f"Failed to initialize RAG: {e}", exc_info=True)
        raise  # Fail fast

    yield

    # Cleanup
    if hasattr(app.state, 'components'):
        if 'metadata_store' in app.state.components:
            app.state.components['metadata_store'].close()

app = FastAPI(lifespan=lifespan)

# Update all endpoints to use app.state
@app.post("/api/chat")
async def chat(request: ChatRequest, app_request: Request):
    retriever = app_request.app.state.retriever
    chatbot = app_request.app.state.chatbot

    if not retriever or not chatbot:
        raise HTTPException(status_code=503, detail="RAG not initialized")
    # ... rest of endpoint
```

---

### Issue #4: Pickle Deserialization - Arbitrary Code Execution

**Location:** `rag_pipeline/bm25_index.py:236`

**Problem:**
```python
def load(self, path: Path = None) -> bool:
    with open(path, 'rb') as f:
        data = pickle.load(f)  # SECURITY RISK!
```

**Impact:** If BM25 index file is tampered with, can execute arbitrary Python code

**Fix - Replace with JSON:**
```python
import json
import numpy as np

def save(self, path: Path = None):
    """Save BM25 index safely using JSON."""
    path = path or (self.config.index_dir / "bm25_index.json")

    data = {
        'tokenized_docs': self.tokenized_docs,
        'doc_freqs': dict(self.doc_freqs),
        'doc_lengths': self.doc_lengths,
        'avg_doc_length': self.avg_doc_length,
        'idf': self.idf,
        'k1': self.k1,
        'b': self.b,
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)

    print(f"💾 Index BM25 sauvegardé dans {path}")

def load(self, path: Path = None) -> bool:
    """Load BM25 index safely from JSON."""
    path = path or (self.config.index_dir / "bm25_index.json")

    if not path.exists():
        return False

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Validate structure
    required_keys = {'tokenized_docs', 'doc_freqs', 'doc_lengths',
                     'avg_doc_length', 'idf', 'k1', 'b'}
    if not all(k in data for k in required_keys):
        raise ValueError(f"Invalid BM25 index format in {path}")

    self.tokenized_docs = data['tokenized_docs']
    self.doc_freqs = defaultdict(int, data['doc_freqs'])
    self.doc_lengths = data['doc_lengths']
    self.avg_doc_length = data['avg_doc_length']
    self.idf = data['idf']
    self.k1 = data.get('k1', 1.5)
    self.b = data.get('b', 0.75)

    print(f"📂 Index BM25 chargé: {len(self.tokenized_docs)} docs, {len(self.idf)} termes")
    return True
```

---

### Issue #5: No Input Validation - DoS Vulnerability

**Location:** `app.py:48`

**Problem:**
```python
class ChatRequest(BaseModel):
    message: str  # No length limits!
    conversation_id: Optional[str] = None
    participant_filter: Optional[str] = None
    # ...
```

**Impact:** Can send gigabyte-sized messages, causing memory exhaustion

**Fix:**
```python
from pydantic import BaseModel, Field, validator

class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User's question or message"
    )
    conversation_id: Optional[str] = Field(
        None,
        max_length=100,
        pattern=r'^[a-zA-Z0-9_-]*$'  # Alphanumeric + dash/underscore only
    )
    participant_filter: Optional[str] = Field(
        None,
        max_length=100
    )
    year_filter: Optional[int] = Field(
        None,
        ge=1900,
        le=2100
    )
    date_start: Optional[str] = Field(
        None,
        pattern=r'^\d{4}-\d{2}-\d{2}$'  # YYYY-MM-DD
    )
    date_end: Optional[str] = Field(
        None,
        pattern=r'^\d{4}-\d{2}-\d{2}$'
    )
    use_reranking: bool = True
    use_hybrid: bool = True
    expand_context: bool = True

    @validator('date_start', 'date_end')
    def validate_date_format(cls, v):
        if v:
            try:
                from datetime import datetime
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Invalid date format, use YYYY-MM-DD')
        return v
```

---

### Issue #6: O(n) Chunk Lookup - Performance Bottleneck

**Location:** `rag_pipeline/advanced_retriever.py:280, 336`

**Problem:**
```python
# Called for EVERY search result
idx = self.vector_store.chunks.index(r.chunk)  # O(n) linear search!

# With 43,000 chunks, this is slow
```

**Impact:** Searches become progressively slower as data grows

**Fix - Build Reverse Index:**
```python
class AdvancedRetriever:
    def __init__(self, embedding_model, vector_store, bm25_index=None,
                 metadata_store=None, reranker=None, config=None):
        self.config = config or default_config
        self.embedding_model = embedding_model
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.metadata_store = metadata_store
        self.reranker = reranker

        # Build reverse index for O(1) lookup
        self._chunk_id_to_index = self._build_chunk_index()

        # Configuration
        self.default_top_k = 5
        self.initial_k = 20
        self.hybrid_alpha = 0.5
        self.context_window = 1

    def _build_chunk_index(self) -> dict:
        """Build reverse index: chunk_id -> index for O(1) lookup."""
        return {
            chunk.chunk_id: idx
            for idx, chunk in enumerate(self.vector_store.chunks)
        }

    def _search_dense(self, query, top_k, allowed_indices):
        """Use O(1) lookup instead of O(n)."""
        # ... existing code ...

        candidates = []
        for r in results:
            # OLD: idx = self.vector_store.chunks.index(r.chunk)  # O(n)
            # NEW: O(1) lookup
            idx = self._chunk_id_to_index[r.chunk.chunk_id]

            if allowed_indices and idx not in allowed_indices:
                continue

            candidates.append((idx, r.score, 0.0, r.score, False))
            # ...

    def _apply_reranking(self, query, candidates, top_k):
        """Use O(1) lookup for reranking."""
        # ... existing code ...

        result = []
        for rr in reranked:
            # OLD: Linear search through candidates
            # NEW: Direct lookup
            idx = self._chunk_id_to_index[rr.chunk.chunk_id]

            # Find matching candidate
            for cand_idx, dense, bm25, combined, expanded in candidates:
                if cand_idx == idx:
                    result.append((idx, dense, bm25, rr.rerank_score, expanded))
                    break

        return result
```

---

## High Priority Issues

### Issue #7: Race Conditions on File I/O

**Location:** `app.py:72-97`

**Problem:**
```python
def load_conversations() -> dict:
    if not CONVERSATIONS_FILE.exists():
        return {}
    with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)  # No file locking!

def save_conversations(conversations: dict):
    with open(CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(conversations, f, ...)  # Concurrent writes = corruption
```

**Impact:** Multiple simultaneous requests can corrupt conversation data

**Fix - Use SQLite Instead:**
```python
# Create conversations_db.py
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Conversation(Base):
    __tablename__ = 'conversations'

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    messages = Column(Text)  # JSON string

# In app.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    engine = create_engine(
        "sqlite:///./conversations.db",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    app.state.db = SessionLocal
    # ... rest of initialization

    yield

    # Cleanup
    engine.dispose()

# Dependency injection
from sqlalchemy.orm import Session

def get_db(request: Request) -> Session:
    db = request.app.state.db()
    try:
        yield db
    finally:
        db.close()

# Use in endpoints
@app.post("/api/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # Database handles concurrent access automatically
    conversation = db.query(Conversation).filter_by(id=conv_id).first()
    # ... rest of logic
```

---

### Issue #8: No Logging Framework

**Location:** Throughout all files

**Problem:**
```python
# All logging uses print statements
print(f"📦 Chargement du modèle {self.config.embedding_model}...")
print(f"✅ Modèle chargé")
```

**Impact:**
- Can't control log levels
- Can't write to files
- No timestamps
- No structured logging for monitoring
- Can't filter by component

**Fix - Add Proper Logging:**
```python
# Create rag_pipeline/logging_config.py
import logging
import sys
from pathlib import Path

def setup_logging(
    level: int = logging.INFO,
    log_file: Path = None,
    format_string: str = None
):
    """Configure application-wide logging."""

    if format_string is None:
        format_string = (
            '%(asctime)s - %(name)s - %(levelname)s - '
            '%(filename)s:%(lineno)d - %(message)s'
        )

    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=handlers
    )

    # Reduce noise from external libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('sentence_transformers').setLevel(logging.WARNING)

# In each module, replace print with logger
import logging
logger = logging.getLogger(__name__)

# Examples:
# OLD: print(f"📦 Chargement du modèle {self.config.embedding_model}...")
# NEW: logger.info(f"Loading embedding model: {self.config.embedding_model}")

# OLD: print(f"⚠️ Erreur: {e}")
# NEW: logger.error(f"Error occurred: {e}", exc_info=True)

# OLD: print(f"✅ Modèle chargé")
# NEW: logger.info("Model loaded successfully")
```

**Usage in app.py:**
```python
from rag_pipeline.logging_config import setup_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup logging first
    setup_logging(
        level=logging.INFO,
        log_file=Path("logs/app.log")
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting application initialization...")
    # ... rest of code
```

---

### Issue #9: Silent Exception Handling

**Location:** `app.py:142-156`, `setup_rag_batch.py:298`

**Problem:**
```python
try:
    retriever, components = create_advanced_retriever(...)
except Exception as e:
    print(f"Erreur lors du chargement: {e}")
    # Application continues with None values!
```

**Impact:** App starts in degraded state without clear indication

**Fix:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize RAG components with proper error handling."""
    logger = logging.getLogger(__name__)

    try:
        config = Config()

        # Validate prerequisites
        if not (config.vector_store_path / "index.faiss").exists():
            logger.error(
                f"FAISS index not found at {config.vector_store_path}. "
                "Run setup_rag_batch.py first."
            )
            raise FileNotFoundError("FAISS index missing")

        logger.info("Loading RAG components...")

        retriever, components = create_advanced_retriever(
            config,
            enable_reranking=True,
            enable_bm25=True,
            enable_metadata=True
        )

        chatbot = ChatBot(retriever, config)

        # Validate initialization
        if components['vector_store'].size == 0:
            raise ValueError("Vector store is empty")

        app.state.retriever = retriever
        app.state.chatbot = chatbot
        app.state.components = components

        logger.info(
            f"✅ RAG initialized successfully with "
            f"{components['vector_store'].size} chunks"
        )

    except FileNotFoundError as e:
        logger.critical(f"Missing required files: {e}")
        raise  # Fail fast - don't start app in degraded state
    except Exception as e:
        logger.critical(f"Failed to initialize RAG: {e}", exc_info=True)
        raise  # Fail fast

    yield

    # Cleanup
    try:
        if hasattr(app.state, 'components'):
            if 'metadata_store' in app.state.components:
                app.state.components['metadata_store'].close()
                logger.info("Closed metadata store connection")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)
```

---

### Issue #10: Streaming Implementation Broken

**Location:** `rag_pipeline/chat.py:172-193`

**Problem:**
```python
def _chat_stream(self, query: str, prompt: str, context: RetrievalContext) -> Generator:
    full_response = []
    for token in self._call_ollama(prompt, stream=True):
        full_response.append(token)
        yield token

    # This doesn't work as expected!
    return ChatResponse(...)  # Generator can't return value like this
```

**Impact:** FastAPI can't properly handle the returned ChatResponse

**Fix:**
```python
# Option 1: Don't return, just yield
def _chat_stream(
    self,
    query: str,
    prompt: str,
    context: RetrievalContext
) -> Generator[str, None, None]:
    """Chat in streaming mode, yields tokens."""
    full_response = []

    try:
        for token in self._call_ollama(prompt, stream=True):
            full_response.append(token)
            yield token
    finally:
        # Update history in finally block
        answer = "".join(full_response)
        self._update_history(query, answer)

# Option 2: Make it async and use proper pattern
async def _chat_stream_async(
    self,
    query: str,
    prompt: str,
    context: RetrievalContext
) -> AsyncGenerator[str, None]:
    """Async streaming chat."""
    full_response = []

    try:
        # Make Ollama call async
        async for token in self._call_ollama_async(prompt, stream=True):
            full_response.append(token)
            yield token
    finally:
        answer = "".join(full_response)
        self._update_history(query, answer)
```

---

## Medium Priority Issues

### Issue #11: Score Normalization Edge Case

**Location:** `rag_pipeline/advanced_retriever.py:352-360`

**Problem:**
```python
if dense_values.max() > dense_values.min():
    dense_norm = (dense_values - dense_values.min()) / (dense_values.max() - dense_values.min())
else:
    dense_norm = dense_values  # Bug: Doesn't normalize to [0,1]
```

**Fix:**
```python
import numpy as np

# Better normalization with edge case handling
eps = 1e-8
dense_range = dense_values.max() - dense_values.min()

if dense_range > eps:
    dense_norm = (dense_values - dense_values.min()) / (dense_range + eps)
else:
    # All scores identical - assign middle value
    dense_norm = np.ones_like(dense_values) * 0.5

# Same for BM25
bm25_range = bm25_values.max() - bm25_values.min()
if bm25_range > eps:
    bm25_norm = (bm25_values - bm25_values.min()) / (bm25_range + eps)
else:
    bm25_norm = np.ones_like(bm25_values) * 0.5
```

---

### Issue #12: Context Window Configuration Mismatch

**Location:** `rag_pipeline/advanced_retriever.py:86, 422`

**Problem:**
```python
# Line 86
self.context_window = 1  # Hardcoded

# But config has:
# config.py, line 42
context_window: int = 2

# Usage at line 422 uses self.context_window instead of config
```

**Fix:**
```python
def __init__(self, ...):
    self.config = config or default_config
    # ...

    # Use config value
    self.context_window = self.config.context_window
```

---

### Issue #13: Fragile Conversation Parsing

**Location:** `rag_pipeline/chunker.py:74-84`

**Problem:**
```python
for i, line in enumerate(lines):
    if line.startswith('# Conversation Instagram avec'):
        metadata['title'] = line.replace('# Conversation Instagram avec', '').strip()
    elif line.startswith('ID:'):
        metadata['conversation_id'] = line.split(':')[1].strip()  # Assumes single ':'
```

**Fix:**
```python
import re
from typing import Dict

def parse_metadata(lines: List[str]) -> Dict[str, str]:
    """Parse metadata with robust error handling."""
    metadata = {
        'conversation_id': '',
        'title': '',
        'participants': []
    }

    for line in lines:
        # Stop at separator
        if line.startswith('=' * 10):
            break

        # Parse title with regex
        if match := re.match(r'^#\s*Conversation Instagram avec\s+(.+)$', line):
            metadata['title'] = match.group(1).strip()

        # Parse ID (handle multiple colons)
        elif match := re.match(r'^ID:\s*(.+)$', line):
            metadata['conversation_id'] = match.group(1).strip()

        # Parse participants
        elif match := re.match(r'^Participants:\s*(.+)$', line):
            participants = [p.strip() for p in match.group(1).split(',')]
            metadata['participants'] = [p for p in participants if p]

        # Parse dates
        elif match := re.match(r'^Date:\s*(\d{4}-\d{2}-\d{2})\s*→\s*(\d{4}-\d{2}-\d{2})$', line):
            metadata['date_start'] = match.group(1)
            metadata['date_end'] = match.group(2)

    return metadata
```

---

### Issue #14: No CORS Configuration

**Location:** `app.py:168`

**Problem:**
```python
app = FastAPI(title="Instagram Assistant API")
# No CORS middleware!
```

**Impact:** Frontend on different domain can't make requests

**Fix:**
```python
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Instagram Assistant API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:8080",  # Production frontend
        # Add your production domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### Issue #15: No Rate Limiting

**Location:** All endpoints

**Problem:** No throttling on API endpoints

**Impact:** Easy to DoS the Ollama server

**Fix:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to endpoints
@app.post("/api/chat")
@limiter.limit("10/minute")  # 10 requests per minute
async def chat(request: ChatRequest, http_request: Request):
    # ... existing code
```

---

## Detailed Fix Implementations

### Full Example: Refactored app.py with All Critical Fixes

```python
"""
Instagram Assistant - FastAPI Application
Refactored with all critical fixes applied.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from slowapi import Limiter
from slowapi.util import get_remote_address

from rag_pipeline.config import Config
from rag_pipeline.advanced_retriever import create_advanced_retriever
from rag_pipeline.chat import ChatBot
from rag_pipeline.logging_config import setup_logging

# Setup logging first
setup_logging(
    level=logging.INFO,
    log_file=Path("logs/app.log")
)
logger = logging.getLogger(__name__)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Request/Response Models with Validation
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: Optional[str] = Field(None, max_length=100, pattern=r'^[a-zA-Z0-9_-]*$')
    participant_filter: Optional[str] = Field(None, max_length=100)
    year_filter: Optional[int] = Field(None, ge=1900, le=2100)
    date_start: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    date_end: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    use_reranking: bool = True
    use_hybrid: bool = True
    expand_context: bool = True

    @validator('date_start', 'date_end')
    def validate_date_format(cls, v):
        if v:
            try:
                from datetime import datetime
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Invalid date format, use YYYY-MM-DD')
        return v

class ChatResponse(BaseModel):
    answer: str
    sources: list
    conversation_id: str

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    logger.info("Starting application initialization...")

    try:
        # Load configuration
        config = Config()

        # Validate prerequisites
        if not (config.vector_store_path / "index.faiss").exists():
            logger.error(f"FAISS index not found at {config.vector_store_path}")
            raise FileNotFoundError("Run setup_rag_batch.py first to create indexes")

        # Initialize RAG components
        logger.info("Loading RAG components...")
        retriever, components = create_advanced_retriever(
            config,
            enable_reranking=True,
            enable_bm25=True,
            enable_metadata=True
        )

        # Initialize chatbot with retriever
        chatbot = ChatBot(retriever, config)

        # Validate
        if components['vector_store'].size == 0:
            raise ValueError("Vector store is empty")

        # Store in app.state (NOT globals!)
        app.state.config = config
        app.state.retriever = retriever
        app.state.chatbot = chatbot
        app.state.components = components

        # Initialize database for conversations
        engine = create_engine(
            "sqlite:///./conversations.db",
            connect_args={"check_same_thread": False}
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        app.state.db = SessionLocal

        logger.info(f"✅ RAG initialized with {components['vector_store'].size} chunks")

    except Exception as e:
        logger.critical(f"Failed to initialize application: {e}", exc_info=True)
        raise  # Fail fast

    yield

    # Cleanup
    try:
        if hasattr(app.state, 'components'):
            if 'metadata_store' in app.state.components:
                app.state.components['metadata_store'].close()
                logger.info("Closed metadata store")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)

# Create FastAPI app
app = FastAPI(
    title="Instagram Assistant API",
    version="1.0.0",
    lifespan=lifespan
)

# Add rate limiting
app.state.limiter = limiter

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
def get_db(request: Request):
    db = request.app.state.db()
    try:
        yield db
    finally:
        db.close()

# Health check endpoint
@app.get("/api/health")
async def health_check(request: Request):
    """Check if RAG system is ready."""
    if not hasattr(request.app.state, 'retriever'):
        raise HTTPException(status_code=503, detail="RAG not initialized")

    return {
        "status": "healthy",
        "chunks": request.app.state.components['vector_store'].size
    }

# Chat endpoint with rate limiting
@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(
    request: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """Process chat request with RAG."""
    retriever = http_request.app.state.retriever
    chatbot = http_request.app.state.chatbot

    if not retriever or not chatbot:
        raise HTTPException(status_code=503, detail="RAG not ready")

    try:
        # Retrieve context
        context = retriever.retrieve(
            query=request.message,
            participant_filter=request.participant_filter,
            year_filter=request.year_filter,
            date_start=request.date_start,
            date_end=request.date_end,
            use_reranking=request.use_reranking,
            use_hybrid=request.use_hybrid,
            expand_context=request.expand_context
        )

        # Build prompt and get response
        prompt = chatbot._build_prompt(request.message, context)
        response_text = chatbot._call_ollama(prompt, stream=False)

        # Format sources
        sources = []
        for r in context.results:
            sources.append({
                "file": r.chunk.file_source,
                "participants": r.chunk.participants,
                "date_start": r.chunk.date_start[:10],
                "date_end": r.chunk.date_end[:10],
                "score": round(r.final_score, 2)
            })

        return ChatResponse(
            answer=response_text,
            sources=sources,
            conversation_id=request.conversation_id or "default"
        )

    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Static files
app.mount("/static", StaticFiles(directory="web/static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse("web/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Security Concerns

### Summary of Security Issues

1. **Pickle deserialization** - Arbitrary code execution (CRITICAL)
2. **No input validation** - DoS via large inputs (HIGH)
3. **No rate limiting** - API abuse (HIGH)
4. **Hardcoded credentials** - If using authenticated Ollama (MEDIUM)
5. **No CORS** - Can be exploited or block legitimate requests (MEDIUM)
6. **File path traversal** - Static files exposure (LOW)

### Security Checklist

```markdown
- [x] Replace pickle with JSON serialization
- [x] Add input validation with Pydantic
- [x] Implement rate limiting
- [ ] Add API authentication (JWT tokens)
- [x] Configure CORS properly
- [ ] Add request ID tracking
- [ ] Implement audit logging
- [ ] Add HTTPS in production
- [ ] Environment variable for secrets
- [ ] Input sanitization for SQL queries
- [ ] Content Security Policy headers
- [ ] Add security headers (helmet equivalent)
```

---

## Performance Optimizations

### Optimization Summary

| Issue | Impact | Fix Complexity | Priority |
|-------|--------|----------------|----------|
| O(n) chunk lookup | High with large datasets | Easy | HIGH |
| Full BM25 scoring | Medium | Medium | MEDIUM |
| Unnecessary normalization | Low | Easy | LOW |
| Duplicate stopwords | Low | Easy | LOW |
| Checkpoint recounting | Medium during setup | Easy | MEDIUM |

### Implementation: Efficient BM25 Scoring

```python
# rag_pipeline/advanced_retriever.py

def _search_hybrid(self, query, top_k, allowed_indices):
    """Optimized hybrid search."""
    # Dense search
    query_embedding = self.embedding_model.encode_single(query)
    dense_results = self.vector_store.search(
        query_embedding,
        top_k=top_k * 3,
        min_score=0.0
    )

    # Build dense dict
    dense_dict = {}
    for r in dense_results:
        idx = self._chunk_id_to_index[r.chunk.chunk_id]  # O(1) lookup
        dense_dict[idx] = r.score

    # BM25 search - get top-k only, not all scores
    if self.bm25_index:
        bm25_results = self.bm25_index.search(query, top_k=top_k * 3)
        bm25_dict = {idx: score for idx, score in bm25_results}
    else:
        bm25_dict = {}

    # Merge indices
    all_indices = set(dense_dict.keys()) | set(bm25_dict.keys())

    # Filter by allowed_indices early
    if allowed_indices:
        all_indices &= allowed_indices

    if not all_indices:
        return []

    # Get score arrays only for selected indices
    indices_list = list(all_indices)
    dense_values = np.array([dense_dict.get(i, 0.0) for i in indices_list])
    bm25_values = np.array([bm25_dict.get(i, 0.0) for i in indices_list])

    # Normalize with edge case handling
    eps = 1e-8
    dense_range = dense_values.max() - dense_values.min()
    bm25_range = bm25_values.max() - bm25_values.min()

    if dense_range > eps:
        dense_norm = (dense_values - dense_values.min()) / (dense_range + eps)
    else:
        dense_norm = np.ones_like(dense_values) * 0.5

    if bm25_range > eps:
        bm25_norm = (bm25_values - bm25_values.min()) / (bm25_range + eps)
    else:
        bm25_norm = np.ones_like(bm25_values) * 0.5

    # Combine scores
    combined = self.hybrid_alpha * dense_norm + (1 - self.hybrid_alpha) * bm25_norm

    # Sort and build candidates
    sorted_indices = np.argsort(combined)[::-1]

    candidates = []
    for i in sorted_indices[:top_k]:
        idx = indices_list[i]
        candidates.append((
            idx,
            float(dense_values[i]),
            float(bm25_values[i]),
            float(combined[i]),
            False
        ))

    return candidates
```

---

## Testing Recommendations

### Unit Tests

```python
# tests/test_chunker.py
import pytest
from rag_pipeline.chunker import Chunker, parse_metadata

def test_parse_metadata_with_missing_fields():
    """Ensure graceful handling of incomplete metadata."""
    lines = [
        "# Conversation Instagram",  # Incomplete title
        "ID:",  # Missing ID
        "Participants: Alice, Bob"
    ]
    metadata = parse_metadata(lines)
    assert metadata['participants'] == ['Alice', 'Bob']

def test_parse_metadata_with_special_characters():
    """Handle unicode, emojis, etc."""
    lines = [
        "# Conversation Instagram avec Marie 🎉",
        "ID: abc-123",
        "Participants: José, François"
    ]
    metadata = parse_metadata(lines)
    assert "Marie 🎉" in metadata['title']

# tests/test_advanced_retriever.py
def test_score_normalization_edge_cases():
    """Test when all scores are identical."""
    from rag_pipeline.advanced_retriever import AdvancedRetriever
    # ... create mock retriever

    # All scores identical
    dense_values = np.array([0.5, 0.5, 0.5])
    # Should return normalized to 0.5, not original values

def test_chunk_lookup_performance():
    """Verify O(1) instead of O(n)."""
    import time
    # ... create retriever with 10k chunks

    start = time.time()
    for _ in range(100):
        idx = retriever._chunk_id_to_index[chunk_id]
    duration = time.time() - start

    assert duration < 0.01  # Should be instant

# tests/test_embeddings.py
def test_device_fallback():
    """Ensure graceful fallback when GPU unavailable."""
    config = Config(use_gpu=True)
    model = EmbeddingModel(config)
    # Should not crash, should log warning

# tests/test_bm25.py
def test_bm25_json_serialization():
    """Verify safe serialization instead of pickle."""
    bm25 = BM25Index()
    bm25.build_index(chunks)
    bm25.save()

    bm25_loaded = BM25Index()
    assert bm25_loaded.load()
    # Verify integrity
```

### Integration Tests

```python
# tests/test_app_integration.py
import pytest
from fastapi.testclient import TestClient
from app import app

@pytest.fixture
def client():
    return TestClient(app)

def test_chat_endpoint_with_invalid_input(client):
    """Test input validation."""
    # Message too long
    response = client.post("/api/chat", json={
        "message": "x" * 10000
    })
    assert response.status_code == 422

    # Invalid date format
    response = client.post("/api/chat", json={
        "message": "test",
        "date_start": "2024/01/01"
    })
    assert response.status_code == 422

def test_rate_limiting(client):
    """Test rate limiting works."""
    # Make 11 requests (limit is 10/minute)
    for i in range(11):
        response = client.post("/api/chat", json={"message": f"test {i}"})
        if i < 10:
            assert response.status_code in [200, 503]
        else:
            assert response.status_code == 429  # Too many requests

def test_concurrent_conversations(client):
    """Test race condition handling."""
    import concurrent.futures

    def make_request(i):
        return client.post("/api/chat", json={
            "message": f"test {i}",
            "conversation_id": "test-conv"
        })

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request, i) for i in range(5)]
        results = [f.result() for f in futures]

    # All should succeed without corruption
    assert all(r.status_code == 200 for r in results)
```

### Load Testing

```python
# tests/test_load.py
import pytest
from locust import HttpUser, task, between

class ChatUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def chat(self):
        self.client.post("/api/chat", json={
            "message": "Tell me about conversations in 2024"
        })

    @task(3)  # 3x more frequent
    def health_check(self):
        self.client.get("/api/health")

# Run with: locust -f tests/test_load.py --host=http://localhost:8000
```

---

## Deployment Checklist

### Pre-Production Checklist

**Critical Fixes**
- [ ] Fix ChatBot constructor mismatch (Issue #1)
- [ ] Remove hardcoded paths (Issue #2)
- [ ] Replace globals with app.state (Issue #3)
- [ ] Replace pickle with JSON (Issue #4)
- [ ] Add input validation (Issue #5)
- [ ] Fix O(n) lookup (Issue #6)

**High Priority**
- [ ] Replace JSON file storage with SQLite
- [ ] Add logging framework
- [ ] Fix silent exception handling
- [ ] Fix streaming implementation
- [ ] Add proper error handling

**Security**
- [ ] Add rate limiting
- [ ] Configure CORS properly
- [ ] Add API authentication (if needed)
- [ ] Use environment variables for secrets
- [ ] Add security headers
- [ ] Review file permissions
- [ ] Audit all user inputs

**Performance**
- [ ] Build chunk index for O(1) lookup
- [ ] Optimize BM25 scoring
- [ ] Add caching where appropriate
- [ ] Profile memory usage
- [ ] Load test with expected traffic

**Observability**
- [ ] Setup structured logging
- [ ] Add health check endpoint
- [ ] Add metrics collection
- [ ] Configure error tracking (Sentry)
- [ ] Add request tracing
- [ ] Setup monitoring dashboard

**Testing**
- [ ] Unit tests for core functions
- [ ] Integration tests for API
- [ ] Load testing with realistic data
- [ ] Security testing
- [ ] Test error scenarios

**Documentation**
- [ ] API documentation (FastAPI auto-generates)
- [ ] Setup/installation guide
- [ ] Configuration guide
- [ ] Troubleshooting guide
- [ ] Architecture documentation

**Infrastructure**
- [ ] Setup production database
- [ ] Configure reverse proxy (nginx)
- [ ] Setup SSL/TLS certificates
- [ ] Configure log rotation
- [ ] Setup backup strategy
- [ ] Plan scaling strategy
- [ ] Setup CI/CD pipeline

### Environment Setup

```bash
# .env.example
USER_NAME=YourName
INSTAGRAM_ASSISTANT_HOME=/path/to/app
OLLAMA_URL=http://localhost:11434
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./conversations.db
CORS_ORIGINS=http://localhost:3000,https://your-domain.com
RATE_LIMIT=10/minute
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directories
RUN mkdir -p rag_data logs

# Expose port
EXPOSE 8000

# Run with gunicorn for production
CMD ["gunicorn", "app:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./rag_data:/app/rag_data
      - ./logs:/app/logs
      - ./conversations.db:/app/conversations.db
    environment:
      - USER_NAME=${USER_NAME}
      - OLLAMA_URL=http://ollama:11434
      - LOG_LEVEL=INFO
    depends_on:
      - ollama

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

volumes:
  ollama_data:
```

### Production Server Setup

```bash
# Using gunicorn with uvicorn workers
gunicorn app:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --log-level info \
    --timeout 120
```

---

## Conclusion

This Instagram Assistant backend has a solid foundation with excellent RAG architecture, but requires critical fixes before production deployment. The main areas needing attention are:

1. **Startup Issues** - Constructor bugs that prevent the app from running
2. **Portability** - Hardcoded paths and configuration
3. **Thread Safety** - Global state management
4. **Security** - Input validation, pickle usage, rate limiting
5. **Performance** - O(n) lookups and inefficient scoring
6. **Observability** - Proper logging and error handling

### Estimated Timeline

- **Critical Fixes (1 week)**: Issues #1-6
- **High Priority (1 week)**: Database migration, logging, error handling
- **Testing & Documentation (3-5 days)**: Unit tests, integration tests, docs
- **Production Hardening (2-3 days)**: Security review, load testing, monitoring

**Total: 2-3 weeks to production-ready state**

### Next Steps

1. Start with the critical fixes in order of severity
2. Add comprehensive testing as you go
3. Implement logging early for better debugging
4. Document changes and configuration
5. Load test before production deployment

The codebase shows good engineering practices and thoughtful design. With these fixes applied, it will be a robust, production-ready RAG system.
