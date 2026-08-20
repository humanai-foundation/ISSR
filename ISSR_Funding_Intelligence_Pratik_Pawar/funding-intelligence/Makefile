.PHONY: install dev test lint run ingest tag serve docker-up \
        harvest-nsf-awards benchmark-disciplines diagnose-separation \
        harvest-openalex annotate-eval-set enrich-foas export-json \
        web-install web-dev web-build

install:
	pip install -r requirements.txt
	python -m spacy download en_core_web_lg
	python -m nltk.downloader wordnet omw-1.4

dev:
	pip install -r requirements-dev.txt

test:
	PYTHONPATH=src pytest tests/ -v --tb=short

lint:
	ruff check src/ tests/
	mypy src/foa_pipeline/

# ── Pipeline Commands ──

ingest-grants:
	PYTHONPATH=src python -m foa_pipeline.cli grants-poll

ingest-nsf-rss:
	PYTHONPATH=src python -m foa_pipeline.cli nsf-rss-poll

ingest-nsf-scrape:
	PYTHONPATH=src python -m foa_pipeline.cli nsf-scrape

parse-pdf:
	PYTHONPATH=src python -m foa_pipeline.cli pdf-parse $(pdf_path)

normalise:
	PYTHONPATH=src python -m foa_pipeline.cli normalise

# Downloads and parses FOA PDFs for both sources. The CLI command is
# enrich-foas; this target used to invoke a non-existent "enrich-grants",
# which broke `make pipeline` partway through.
enrich-foas:
	PYTHONPATH=src python -m foa_pipeline.cli enrich-foas

setup-ontology:
	PYTHONPATH=src python -m foa_pipeline.cli setup-ontology

tag:
	PYTHONPATH=src python -m foa_pipeline.cli tag-all

export-csv:
	PYTHONPATH=src python -m foa_pipeline.cli export-csv

export-json:
	PYTHONPATH=src python -m foa_pipeline.cli export-json

precompute-embeddings:
	PYTHONPATH=src python -m foa_pipeline.cli precompute-embeddings

# ── Evaluation ──

# Harvests NSF awards as a directorate-labelled corpus. Awards are written to
# the evaluation directory only -- they are not FOAs and must never enter the
# FOA database. See src/foa_pipeline/ingestion/nsf_awards.py.
harvest-nsf-awards:
	PYTHONPATH=src python -m foa_pipeline.cli harvest-nsf-awards

# Vendors the CC0 OpenAlex field taxonomy to data/ontology/. The resulting CSV
# is staged, NOT loaded: see Documentation/EVALUATION.md 4g before registering it.
harvest-openalex:
	PYTHONPATH=src python -m foa_pipeline.cli harvest-openalex

benchmark-disciplines:
	PYTHONPATH=src python -m foa_pipeline.cli benchmark-disciplines

diagnose-separation:
	PYTHONPATH=src python -m foa_pipeline.cli diagnose-separation

# Drafts SILVER labels for eval_set_50.json with the local LLM. Never the gold
# set, and never a reported metric -- tuning signal only.
annotate-eval-set:
	PYTHONPATH=src python -m foa_pipeline.cli annotate-eval-set

# ── Full Pipeline ──

pipeline: ingest-grants ingest-nsf-rss normalise enrich-foas tag export-csv export-json

# ── Server ──

serve:
	PYTHONPATH=src uvicorn foa_pipeline.api.app:app --reload --port 8000

# ── Web Frontend (Next.js, web/) ──
# Runs as its own server on :3000, separate from the API on :8000 -- see
# Documentation/MATCHING.md / the frontend rewrite plan for why. `make serve` must also be
# running (or the containerized api service) for pages to have data to show.

web-install:
	cd web && npm install

web-dev:
	cd web && npm run dev

web-build:
	cd web && npm run build

# ── Docker ──

docker-up:
	docker-compose up --build -d

docker-down:
	docker-compose down
