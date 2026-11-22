# ==============================================================================
# Web2API - Master Project Makefile
# ==============================================================================

.PHONY: help install setup test lint run bridge mock chat clean

VENV ?= .venv
PYTHON ?= $(shell if [ -f $(VENV)/bin/python ]; then echo $(VENV)/bin/python; else echo python3; fi)
PYTEST ?= $(PYTHON) -m pytest
FLAKE8 ?= $(PYTHON) -m flake8

help:
	@echo "Web2API Commands:"
	@echo "  make install  - Run unified one-step installer (install.sh)"
	@echo "  make bridge   - Start Web2API Extension Bridge Server (Port 8000)"
	@echo "  make test     - Run test suite (pytest)"
	@echo "  make lint     - Run flake8 code linter"
	@echo "  make mock     - Start mock browser extension harness"
	@echo "  make chat     - Start interactive streaming chat CLI"
	@echo "  make openai   - Run official OpenAI Python SDK conformance test"
	@echo "  make clean    - Remove virtualenv and temporary build artifacts"

install:
	@chmod +x install.sh
	@./install.sh

setup: install

test:
	$(PYTEST) tests/ sdks/python/tests/

lint:
	$(FLAKE8) bridge_server.py harness.py tool_parser.py test_openai_client.py scripts/code_review.py tests/ sdks/python/

bridge:
	$(PYTHON) bridge_server.py

mock:
	$(PYTHON) harness.py mock

chat:
	$(PYTHON) harness.py chat

openai:
	$(PYTHON) test_openai_client.py

clean:
	rm -rf $(VENV) .pytest_cache reports/review*.md build/ dist/ *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
