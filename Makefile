# Environment configuration
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Default target
.PHONY: help
help:
	@echo "Instagram Assistant - Makefile Helper"
	@echo "====================================="
	@echo "Usage: make [target]"
	@echo ""
	@echo "Setup:"
	@echo "  install        Create venv and install dependencies"
	@echo "  setup-env      Run interactive environment setup"
	@echo ""
	@echo "Running:"
	@echo "  run            Start the FastAPI backend"
	@echo "  dev            Start the FastAPI backend with hot reload"
	@echo "  cli            Start the CLI chat"
	@echo "  cli-query Q=x  Run a single CLI query (make cli-query Q='your query')"
	@echo ""
	@echo "Indexing:"
	@echo "  index          Run full indexing pipeline"
	@echo "  update         Run incremental update"
	@echo "  status         Check indexing status"
	@echo ""
	@echo "Evaluation:"
	@echo "  eval-retrieval Run retrieval evaluation"
	@echo "  eval-gen       Run generation evaluation"
	@echo ""
	@echo "Utilities:"
	@echo "  stats          Show conversation statistics"
	@echo "  clean          Remove cache files"

# Setup
.PHONY: install
install:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt
	@echo "✅ Setup complete. Use 'make run' to start."

.PHONY: setup-env
setup-env:
	$(PYTHON) scripts/setup/setup_env.py

# Application
.PHONY: run
run:
	$(PYTHON) app.py

.PHONY: dev
dev:
	$(PYTHON) app.py --reload

.PHONY: cli
cli:
	$(PYTHON) cli.py

.PHONY: cli-query
cli-query:
	$(PYTHON) cli.py --prompt "$(Q)"

# RAG Pipeline
.PHONY: index
index:
	$(PYTHON) scripts/setup/setup_rag.py

.PHONY: update
update:
	$(PYTHON) scripts/maintenance/update_index.py

.PHONY: status
status:
	$(PYTHON) scripts/setup/setup_rag.py --status

# Evaluation
.PHONY: eval-retrieval
eval-retrieval:
	$(PYTHON) -m eval.eval_retrieval

.PHONY: eval-gen
eval-gen:
	$(PYTHON) -m eval.eval_generation

# Utilities
.PHONY: stats
stats:
	$(PYTHON) scripts/analysis/conversation_stats.py

.PHONY: check-enrich
check-enrich:
	$(PYTHON) scripts/utils/check_enrichment_status.py

.PHONY: clean
clean:
	rm -rf __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
