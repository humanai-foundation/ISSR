# Contributing

Thanks for your interest in ISSR Funding Intelligence. This project began as a
Google Summer of Code 2026 project for the University of Alabama's Institute for
Social Science Research, and it is built to be picked up and extended by people
who weren't there when it was written.

This guide covers how to get set up, what the codebase expects, and — most
importantly — how to change the semantic tagging engine without silently
degrading its accuracy.

---

## Getting set up

```bash
git clone <your-fork-url>
cd funding-intelligence

python -m venv .venv
source .venv/bin/activate

pip install -r requirements-dev.txt      # includes runtime deps
python -m spacy download en_core_web_lg
python -m nltk.downloader wordnet omw-1.4
playwright install chromium              # only needed for NSF scraping

cp .env.example .env
```

**Layer 3 (LLM disambiguation) is optional.** It needs a local
[Ollama](https://ollama.com) server with `mistral:7b-instruct` pulled. Without
it the pipeline logs a warning and runs with Layer 1 + Layer 2 only — that path
is supported and tested, so don't feel obliged to install Ollama to contribute.

Verify your setup:

```bash
make test        # pytest
make lint        # ruff + mypy
```

---

## Repository layout

The package is grouped by pipeline stage, in the order data flows:

| Package | Responsibility |
|---|---|
| `ingestion/` | Source connectors: Grants.gov API, NSF RSS, NSF scraping, PDF download |
| `parsing/` | Layout-aware PDF extraction and LLM field extraction |
| `normalisation/` | Canonical schema, normalisation, JSON Schema validation |
| `ontology/` | Controlled vocabulary store and synonym expansion |
| `tagging/` | Three-layer tagging engine and tag provenance |
| `matching/` | FAISS vector index and hybrid researcher-profile ranking |
| `storage/` | SQLite application database and JSONL helpers |
| `evaluation/` | Evaluation driver, scoring metrics, label generation |
| `export/` | CSV/JSON export for downstream consumers |
| `api/` | FastAPI application serving the web frontend |

`config.py`, `cli.py`, and `logging_setup.py` stay at package root.

Prefer importing from a subpackage's public surface:

```python
from foa_pipeline.tagging import TaggerPipeline      # yes
from foa_pipeline.tagging.pipeline import TaggerPipeline   # works, but reaches inside
```

If you add a module, export its public names from that package's `__init__.py`
and confirm the names actually resolve — a mismatch there breaks at runtime
while unit tests stay green (this has happened; see the restructure commit).

---

## Changing the tagging engine

This is the part that needs the most care. Tagging quality is the project's
core contribution, and it is easy to make a change that looks reasonable and
quietly costs accuracy.

**Always measure before and after.** The gold-standard evaluation is the
arbiter:

```bash
PYTHONPATH=src python -m foa_pipeline.cli setup-ontology       # if you changed synonyms/ontology
PYTHONPATH=src python -m foa_pipeline.cli precompute-embeddings # if you changed concept descriptions
PYTHONPATH=src python -m foa_pipeline.cli tag-all
PYTHONPATH=src python -m foa_pipeline.cli evaluate --gold
```

Record the before and after numbers in your PR description. A change that
lowers global F1 needs a stated reason to keep it.

### Rules that exist for a reason

- **Never report metrics from `eval_set_50.json`.** It is an LLM-generated
  *silver* standard produced by the same model family used for Layer 3, so
  scoring against it is partly circular. Use it for threshold tuning only.
  Headline numbers come from the 20-FOA hand-labelled `eval_set_gold.json`.
  See [EVALUATION.md](Documentation/EVALUATION.md).
- **Re-run `setup-ontology` after editing synonyms.** Synonyms are stored in
  SQLite; editing `ontology/synonyms.py` alone changes nothing until the store
  is rebuilt.
- **Re-run `precompute-embeddings` after editing concept descriptions.** Layer 2
  embeds `label + description + top-5 synonyms`, and the embeddings are cached.
- **Adding a synonym is a precision risk.** Generic terms match everywhere.
  Check `data/evaluation/false_positives.json` after any synonym change; if a
  term fires on incidental text, add it to `NOISY_SYNONYMS`.
- **Prefer a per-concept threshold over raising a whole category's.** A single
  noisy concept shouldn't cost recall across its category. `cosine_thresholds`
  accepts a `concept_id` key that takes precedence over the category default.

### Working with the ontology

Concepts live in CSVs under `data/ontology/`. To add one: add the row, run
`setup-ontology`, run `precompute-embeddings`, re-tag, and evaluate. Document
the rationale in [ONTOLOGY.md](Documentation/ONTOLOGY.md) — the design reasoning matters as
much as the concept itself.

---

## Code style

- `make lint` must pass. Ruff config lives in `pyproject.toml`.
- The project targets **Python 3.9**. Ruff will not suggest `X | None` or
  builtin generics for this reason — use `typing.Optional` / `typing.Dict`.
- Type hints on public functions. `mypy` currently reports pre-existing findings
  in older modules; please don't add new ones.
- Comments should explain *why*, not restate the code. The most valuable
  comments here record non-obvious constraints — see the OpenMP note in
  `__init__.py` or the `db=None` rationale in `api/deps.py`.

## Tests

- Tests live in `tests/`. Unit tests should not require a populated database,
  network access, or Ollama.
- Anything touching the API should use `TestClient` with `dependency_overrides`,
  and open a **per-request** database connection — SQLite refuses connections
  shared across threads, and FastAPI dispatches sync routes on a threadpool.
- Three tests in `tests/test_tagger_l1.py` are currently failing and predate
  current work. They're known; don't be alarmed, and please don't paper over
  them with weakened assertions.

## Pull requests

1. Branch from `main`.
2. Keep the change focused — a bug fix and a refactor belong in separate PRs.
3. Run `make test` and `make lint`.
4. If you touched tagging, include before/after evaluation numbers.
5. Explain the reasoning in the PR description, especially for anything
   non-obvious. Future maintainers read PR history to understand decisions.

Reporting a bug you don't intend to fix is a genuinely useful contribution —
please open an issue.

## Questions

Open an issue with the `question` label. For anything security-related, see
[SECURITY.md](SECURITY.md) instead.
