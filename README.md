# Instagram Assistant

**Explore your digital memories. Privately. Locally.**

Turn your Instagram archive into a searchable, interactive knowledge base. Ask questions like *"When did we go to Italy?"*, *"What music did we talk about last year?"*, or *"Summarize my relationship with Alex"*.

Running 100% on your machine using advanced AI (Ollama + RAG).

---

## ✨ Features

- **💬 Natural Conversation**: Chat with your history as if it were a person.
- **🔍 Deep Search**: Finds answers even if you don't remember the exact words (semantic search).
- **📅 "Big Picture" Views**: Automatically generates monthly summaries and relationship overviews.
- **🔒 Private by Design**: No data leaves your computer. Your messages, your business.
- **🖥️ Modern Interface**: A beautiful React application to browse, filter, and visualize your chats.

## 🚀 Quick Start

### Prerequisites
- **Python 3.13+**
- **Node.js** (for the frontend)
- **Ollama** (installed and running)

### 1. Setup Environment
```bash
# Clone the repo and enter directory
python setup_env.py  # Interactive configuration
pip install -r requirements.txt
```

### 2. Import Data
Put your Instagram export JSON files in the folder configured during setup (default: `instagram_conversations/`).

```bash
# Convert JSON to text
python instagram_to_text.py

# Build the AI index (may take a while)
python setup_rag.py
```

### 3. Run the App

**Option A: Web Interface (Recommended)**
```bash
# Terminal 1: Backend
python app.py

# Terminal 2: Frontend
cd frontend && pnpm install && pnpm dev --open
```

**Option B: Terminal Chat**
```bash
python cli.py
```

---

## 📚 Documentation

- **[Full Documentation](docs/README.md)**: The central hub for all project docs.
- **[Installation Guide](docs/QUICKSTART.md)**: Detailed step-by-step setup.
- **[Command Reference](docs/COMMANDS.md)**: All available CLI commands.
- **[Architecture](docs/ARCHITECTURE.md)**: How the system works.
- **[RAG Pipeline](docs/rag/README.md)**: Deep dive into the AI logic.
- **[Development](docs/DEVELOPMENT.md)**: For contributors.

## 🛠️ Common Tasks

**Updating your Archive:**
Use the merge tool to combine new exports with old ones without losing history.
```bash
python merge_instagram_exports.py old_export/ new_export/ -o merged/
```
Then run `python update_index.py` to add only the new messages.

**Checking System Status:**
```bash
python setup_rag.py --status
```

## 🏗️ Architecture Highlight

The system uses a **Two-Stage RAG Pipeline**:
1.  **Indexing:** Your chats are "read" by an AI (Enricher Agent) to understand context, emotion, and topics.
2.  **Retrieval:** When you ask a question, we use Hybrid Search (Keywords + Meaning) to find the best answers.

*See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full diagram.*

## 📄 License

MIT License. Built with ❤️ for privacy and nostalgia.