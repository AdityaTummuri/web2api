# ==============================================================================
# Web2API - Master Project Makefile
# ==============================================================================

.PHONY: help install setup test lint run bridge mock chat clean keys android-install android-start android-doctor

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
	@echo "  make keys     - Generate this install's private API keys (api.txt)"
	@echo ""
	@echo "Android (run inside Termux on the phone, see docs/install-android.md):"
	@echo "  make android-install  - Install the lightweight server in Termux"
	@echo "  make android-start    - Start the server (WEB2API_MODE=ssh|tailscale)"
	@echo "  make android-doctor   - Health check (server, extension, keys, memory)"

install:
	@chmod +x install.sh
	@./install.sh

setup: install

test:
	$(PYTEST) tests/ sdks/python/tests/

lint:
	$(FLAKE8) bridge_server.py web2api_keys.py harness.py tool_parser.py test_openai_client.py scripts/code_review.py tests/ sdks/python/

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

keys:
	$(PYTHON) web2api_keys.py generate

android-install:
	bash scripts/android/install-termux.sh --with-ssh

android-start:
	bash scripts/android/start-android.sh

android-doctor:
	bash scripts/android/doctor.sh
