PY := ./.venv/bin/python
PIP := $(PY) -m pip

.PHONY: install install-embed ingest retrieve run test eval costs clean

install:  ## Create venv and install core deps
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-embed:  ## Optional: real local embeddings (fastembed)
	$(PIP) install -r requirements-optional.txt

ingest:  ## Build/rebuild both indexes (support KB + services KB)
	$(PY) -m scripts.ingest_cli

retrieve:  ## Day 1 acceptance: top-k for 5 hand-picked questions
	$(PY) -m scripts.retrieve_cli

run:  ## Serve the API (http://127.0.0.1:8000/docs)
	$(PY) -m uvicorn app.main:app --reload

test:  ## Run the test suite
	$(PY) -m pytest -q

eval:  ## Run the eval harness (accuracy + failure breakdown)
	$(PY) -m scripts.eval_cli

costs:  ## Daily cost rollup over recorded traces
	$(PY) -m scripts.costs_cli

clean:  ## Remove the built indexes
	rm -rf data/index data/services_index
