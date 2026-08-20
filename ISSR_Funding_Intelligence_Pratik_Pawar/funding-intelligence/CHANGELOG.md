# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project was developed for Google Summer of Code 2026 under the HumanAI
Foundation, for the University of Alabama's Institute for Social Science
Research (ISSR).

---

## [Unreleased]

### Added
- `POST /api/match` — grant matching exposed via the API, not just the CLI.
  Wraps the existing hybrid score (0.7 cosine similarity + 0.3 ontology tag
  overlap, `Documentation/MATCHING.md`) and, when `explain: true` (the default) and a local
  LLM is reachable, layers a plain-language explanation and a `strong`/
  `moderate`/`weak` relevance rating onto the top `MATCH_EXPLAIN_TOP_K`
  results (`matching/explain.py`, new). The reviewed window is re-sorted by
  relevance but a candidate outside it can never be promoted — bounds both
  the LLM's influence and worst-case latency. Every failure (Ollama down,
  timeout, malformed response) degrades to a deterministic templated
  sentence; the response always carries `llm_available` so a caller can be
  honest about degraded mode. See `Documentation/MATCHING.md`'s new "LLM Match
  Explanations" section for the full contract, including two pre-existing
  bugs this work surfaced and fixed (below).
- Frontend: the "Semantic Match" view now calls `/api/match` instead of the
  cosine-only `/api/search/semantic`, and renders the hybrid score, the
  cosine/tag-overlap breakdown, matched tag chips, and — for the top results
  — an AI explanation box with a colour-coded relevance badge. Verified with
  a real Ollama instance and a live Playwright browser session, not just unit
  tests: screenshots confirm cards, explanations, and the detail modal all
  render correctly.
- `ontology/store.py`: `OntologyStore.__init__` takes an optional
  `check_same_thread` parameter, defaulting to the existing (safe) behaviour.
  Needed because the API now caches a single `TaggerPipeline` — and the
  `OntologyStore` it holds — across requests that FastAPI may dispatch on
  different threadpool threads; see the docstring for why this is safe (the
  store is read-only from the API's perspective after `initialize()`).
- `ingestion/nsf_awards.py` — NSF Award Search connector producing an
  agency-labelled evaluation corpus (~1,250 abstracts whose research directorate
  NSF assigned itself). Written to the evaluation directory only: awards are a
  different genre from FOAs and must never enter `foa_records`. Crosswalks are
  explicit rather than derived from abbreviations, because NSF reports `CSE` for
  Computer & Information Science and `O/D` for the Office of the Director.
- `evaluation/discipline_benchmark.py` — ranks the eight directorates per award
  and reports top-1/top-3 accuracy, MRR, macro F1 and a confusion matrix. Strict
  scoring uses the managing directorate; lenient also accepts a co-funder, since
  9.9% of awards are co-funded. Includes a deterministic `tune`/`eval` split so
  concept-description edits are never reported on the awards that motivated them.
- `export/json_exporter.py` + `cli export-json` — JSON export of the tagged
  dataset. The scope of work asks for JSON *and* CSV; only CSV was written to
  disk, with JSON available solely as an API response, which requires running a
  server and so is not a reproducible artefact. Output is key-sorted and
  byte-stable across runs.
- `ingestion/openalex.py` + `ontology/openalex_crosswalk.py` — vendors the CC0
  OpenAlex field taxonomy (26 fields, 4 domains) to `data/ontology/` and maps
  all eight NSF directorates onto it. The CSV is **staged, not registered**: a
  test asserts `load_all_ontologies` never picks it up, because adding a sixth
  category while no eval set carries an OpenAlex label would make every
  prediction in it a false positive and collapse global gold F1. It supplies
  descriptions from an external authority, synonyms for 23 of 26 fields, and
  the first real `parent_id` values in the project — which would activate the
  dormant hierarchy propagation. See `Documentation/EVALUATION.md` §4g.
- Namespaced evaluation error logs (`false_positives_gold.json` /
  `_silver.json`, etc.). Both runs previously shared filenames, so a silver run
  silently replaced the gold error analysis that `Documentation/EVALUATION.md` §5 documents.
  `diagnose-separation` gains `--eval-set`, defaulting to gold.
- `research_discipline` prompt in `evaluation/synthetic_annotator.py`, plus
  per-category annotation. The silver set was annotated before that category
  existed, so it scored 0/0/0 there by construction and any tuning against it
  was blind to the project's second-best category. Topping it up required
  replacing the "skip any FOA that already has tags" rule — with all 46 already
  labelled in four categories, it would have skipped every one forever. A run
  now touches only FOAs missing the requested category. 52 discipline tags
  added across 38 of 46 FOAs; the silver set now scores `research_discipline`
  at F1 0.368, second of five and matching the gold set's ordering.
- `annotation_provenance` on every silver-set FOA, recording which categories
  were model-generated, by which model, and when. The labels live in a field
  called `human_tags` for runner compatibility, so without this there was
  nothing in the file distinguishing a model's guess from a person's judgement.
- `normalisation/boilerplate.py` — administrative boilerplate removal before
  tagging. Only HTML markup stripping is enabled by default; the text-level
  pattern groups (eligibility blocks, deadline tables, PAPPG references) are
  retained but disabled because measurement showed they don't improve tagging.
  See `Documentation/EVALUATION.md` §4b for why, and the module docstring for per-group
  numbers.
- `grant_matcher.py` — researcher profile → ranked FOA matching using the hybrid
  relevance score (`0.7 × cosine + 0.3 × tag_overlap`) documented in
  `Documentation/MATCHING.md`. Retrieves a wider FAISS candidate pool than requested before
  re-ranking, so tag overlap can genuinely promote results rather than only
  reorder the top-k. Every result carries `cosine_score`, `tag_overlap_ratio`,
  `matched_tags`, and `hybrid_score` so a ranking can be explained.
- `Documentation/ANNOTATION_CODEBOOK.md` — annotation guidelines and inter-annotator agreement
  protocol for producing a multi-annotator gold standard.
- `tests/test_api.py` — 29 tests covering the previously untested FastAPI layer
  (routes, filtering, pagination, validation, export, OpenAPI registration).
- `tests/test_grant_matcher.py` — 19 tests for the hybrid matching logic.
- Per-concept cosine threshold overrides in `config.py`'s `cosine_thresholds`,
  checked ahead of the per-category threshold.
- `LICENSE` (Apache 2.0) and this changelog.

### Changed
- `cli search` and `cli evaluate` now perform real work. Both previously
  accepted their arguments and only logged a message.
- FAISS index and embedding model are cached per process in the API layer
  instead of being reloaded on every `/api/search/semantic` request
  (~3.3s → ~0.015s per request).
- `VectorIndex.search()` accepts an optional per-call `Database`, so a shared
  cached index can use request-scoped connections rather than holding one
  (SQLite connections cannot cross threads).
- `Documentation/ONTOLOGY.md` documents the `research_discipline` (NSF Directorates) category
  and records that it supersedes UN SDGs for domain classification, with the
  measured F1 gap as justification. Concept count corrected 76 → 84.
- `Documentation/EVALUATION.md` documents `eval_set_50.json` as an LLM-generated *silver*
  standard that cannot substitute for a second human annotator.
- Enriched `research_methods.csv` descriptions for concepts that were producing
  false negatives.

### Fixed
- **`match_profile_to_foas` never forwarded its `db` argument into
  `vector_index.search()`.** Worked by accident from the CLI, which always
  constructs a `VectorIndex` with a database bound at construction; the
  API's cached, cross-request index has no database of its own by design
  (`api/deps.py`), so every API-driven match request raised
  `ValueError: VectorIndex has no Database`. No unit test caught it — every
  test double for `VectorIndex.search()` accepted whatever arguments it was
  given rather than validating the real signature. Found by running the
  actual server against actual data, not by the test suite. Now fixed, with
  a regression test in both `test_grant_matcher.py` and `test_api.py`
  asserting the forwarding happens.
- **The "Semantic Match" UI's similarity threshold defaulted to 0.50**, but
  real cosine scores between a short profile and an FOA's full text commonly
  top out around 0.30–0.35 for genuinely relevant results — the same
  compressed-similarity phenomenon already documented for tag-concept
  cosines. At the old default, a realistic query could silently return zero
  results with no indication why. This reproduces identically on the
  pre-existing `/api/search/semantic` endpoint; it predates this session's
  changes and was only caught by driving the real UI end-to-end in a
  browser. Default is now 0 (no pre-filter) — relevance is communicated by
  the LLM tier and hybrid score instead, which degrade gracefully rather
  than vanishing.
- **Layer 1 rejected a match *after* marking its concept as seen**, so the first
  rejected occurrence consumed the concept's single slot and any later
  legitimate mention was never considered — "energy-efficient components …
  energy remains the central concern" returned no tag at all. The
  `excluded_spans` check was already ordered correctly; the dependency checks
  were not. This is a recall defect in its own right and a prerequisite for the
  scope filters below, which would otherwise have destroyed valid later matches.
- **Layer 1 had no notion of aboutness**, giving it 0.412 precision on the gold
  set (21 TP / 30 FP) despite being exact string matching — every match was a
  real occurrence of the word. `out_of_scope_context` adds five filters
  (`stem_idiom`, `referral`, `agency_mission`, `permissive`, `proper_name`) for
  contexts where a term names something other than the opportunity's subject: an
  acronym expansion, a redirect to another programme, agency mission
  boilerplate, an optional technique, a proper name. Validated against all 51
  gold matches — removes 9 false positives, no true positives. Layer 1 precision
  0.412 → **0.500**. Two candidate rules were measured and rejected: general
  acronym-gloss detection (0 FP, 2 TP — it discards "Directorate for Engineering
  (ENG)") and enumeration membership (one list yields a TP and an FP).
- **`nsf_eng` carried WordNet synonyms of the verb "to engineer"** —
  `mastermind`, `orchestrate`, `organise`, `organize`, `engine room`, `direct` —
  plus `technology`, the single largest source of Layer 1 false positives, which
  fired on "the sociology of science and technology" and on the **TIP
  directorate's own name** although NSF runs Engineering and Technology,
  Innovation and Partnerships separately. All were exclusive to `nsf_eng`.
  `accessibility` was blacklisted from People with Disabilities on the same
  basis. Gold F1 0.517 → **0.527** (P 0.427 → 0.442, recall unchanged).
  See Documentation/EVALUATION.md §4h — including the measurement that the top-3-per-category
  cap re-admits five of the nine removals through Layer 2.
- **`source_url` was null on every Grants.gov record** (115 of 136), a field the
  scope of work lists as required. The search API returns no link of any kind —
  `raw_url` is always None and the fetch payload's `assistURL` is empty — so it
  is now derived from the opportunity ID. The URL pattern was verified rather
  than assumed: the site is a single-page app that returns HTTP 200 for any
  path including nonsense IDs, so confirmation came from finding the matching
  opportunity number in the fetched page. Coverage is now 136/136.
- **The CSV export's `eligibility` column was empty for every row.** The
  exporter read `foa["eligibility"]`, but `list_foas` returns
  `eligibility_description` and no such key, so eligibility text — another
  required field — never reached the deliverable despite being present on 65
  records. It now falls back to the description.
- **`make pipeline` was broken.** It invoked `enrich-grants`, which is not a
  CLI command (the command is `enrich-foas`), so the documented one-command
  update workflow failed partway through. All seven steps now resolve.
- **`tag-all` skipped closed FOAs, making the gold metric decay with the
  calendar.** Status is recomputed from the close date on every `normalise`, so
  an expiring FOA silently left the tagging set and all of its tags became false
  negatives. One gold FOA expiring took global F1 from 0.517 to 0.500 with no
  change to the tagger. `tag-all` now covers all statuses (`--open-only`
  restores the old behaviour); search is unaffected because the FAISS index
  filters to open FOAs separately.
- **JSON Schema validation had been silently disabled since the package
  restructure.** `validator.py` located `foa_schema.json` by a fixed number of
  `.parent` hops; moving the module one directory deeper made that resolve to
  `src/data/`, which does not exist. `load_schema` then fell back to a
  permissive minimal schema, leaving 20 of 27 properties unvalidated — every
  money field, date and free-text field — with only a log line as a symptom.
  The path is now found by walking up, so the same class of move cannot break
  it, and a test asserts the real schema is the one loaded. No existing record
  fails the restored validation (136/136 pass).
- **Stale tags corrupted every evaluation comparison.** `tag-all` never cleared
  `foa_tags` before re-tagging, and `save_tags` uses `INSERT OR REPLACE` keyed
  on `(foa_id, concept_id, source_layer)` — so any concept that stopped being
  emitted after a threshold or synonym change left its old row behind forever.
- **Stale synonyms likewise persisted.** `setup-ontology` never cleared
  `ontology_synonyms`, and `add_synonyms` uses `INSERT OR IGNORE`, so removing a
  synonym in code had no effect on the database.
- **Cross-category synonym leakage.** `synonym_expander.py` matched
  `ABBREVIATIONS` by substring (`label_lower in full_form`), so e.g. the GREAT
  Act concept "Health" silently inherited synonyms authored for the unrelated
  SDG "Good Health and Well-being". Now requires an exact match.
- **Segfault when tagging and vector search ran in one process.** faiss and
  spaCy/torch each ship an OpenMP runtime; loading both aborts on macOS with
  `OMP: Error #15` and no traceback (exit 139). OpenMP threads are now capped in
  the package `__init__` before those libraries load.
- **Synthetic annotator silently produced empty labels.** Its Ollama response
  parser only read dict *values*, but the model sometimes returns
  `{concept_id: [...]}` with the ID as the *key*, so every tag failed validation.
  Only 16 of 46 eval entries had labels before this fix. A guard was also added
  to discard responses that echo back more than half a category's concept list.
- Removed noisy synonyms confirmed as false-positive triggers: `equity`
  (financial/DEI homonym), bare `learning` (matched inside "machine learning"),
  bare `statistics` (matched organisation names), `job creation`.
- `tagger_l1_spacy.py` now rejects the `npadvmod` dependency, catching
  hyphenated compound-adjective false positives such as "energy-efficient".
- `tagger_l3_llm.py` parses Ollama JSON mode instead of substring-matching raw
  generation text, with the old heuristic retained as a fallback.
- `mine-synonyms` queried a non-existent `tag_evidence` table (real table:
  `foa_tags`).
- Removed a dead duplicate `prompts/disambiguation.txt`; the pipeline reads
  `data/prompts/disambiguation.txt`.

### Evaluation
Gold-standard metrics (20-FOA hand-labelled set) across this work:

| Metric | Before | After |
|---|---|---|
| Precision | 0.371 | 0.427 |
| Recall | 0.642 | 0.654 |
| F1 | 0.471 | **0.517** |

Layer 2 separation AUC 0.633 → 0.666 (added as a second metric because F1 on an
81-tag set cannot resolve changes this small — see `Documentation/EVALUATION.md` §4c).

Largest per-category gain: `method` F1 0.250 → 0.462. See `Documentation/EVALUATION.md` §4a,
§4b, and §4c for the per-change breakdown, including several candidate changes
that were tested and rejected for making held-out F1 worse.

#### Discipline benchmark (NSF award corpus, 1,248 awards)

A second, independent benchmark added because the gold set carries only ~3
examples per NSF directorate — too few for any per-concept claim. Layer 2 ranking
over the eight directorates:

| Metric | Value |
|---|---|
| Top-1 accuracy (strict) | 0.639 |
| Top-3 accuracy (strict) | 0.884 |
| Mean reciprocal rank | 0.774 |
| Macro F1 | 0.572 |

This immediately surfaced a defect invisible at gold-set scale: **Engineering
recall 0.014** (2 of 146), with its concept vector ranking sixth of eight on
awards NSF itself labelled Engineering. See `Documentation/EVALUATION.md` §4e.

Rewriting the Engineering description fixed it, measured on a held-out half of
the corpus that played no part in choosing the wording (n=615):

| Metric | Before | After |
|---|---|---|
| Top-3 accuracy (strict) | 0.885 | 0.911 |
| Macro F1 | 0.553 | 0.568 |
| Engineering F1 | 0.026 | 0.154 |
| Engineering recall | 0.013 | 0.092 |

Rewriting *all eight* directorate descriptions was tried first and **rejected**:
it redistributed error rather than reducing it (four categories better, four
worse, top-1 0.639 → 0.613), and its apparent Engineering gain came largely from
degrading Engineering's competitors. See `Documentation/EVALUATION.md` §4f.

---

## [1.0.0] — 2026-07-05 (midterm)

### Added
- Hybrid ingestion: Grants.gov REST API poller, NSF RSS change detector, and
  Playwright-based NSF scraper.
- Layout-aware PDF parsing (pymupdf4llm primary, pdfplumber for tables,
  pdfminer.six fallback) plus an async PDF downloader.
- Schema normalisation across sources with Draft-7 JSON Schema validation.
- SQLite-backed ontology store with WordNet synonym expansion.
- Three-layer semantic tagging: spaCy PhraseMatcher (L1), all-mpnet-base-v2
  embeddings (L2), Mistral-7B disambiguation via Ollama (L3), with CFDA
  crosswalk recall backstop and full tag provenance.
- FAISS `IndexFlatIP` vector index.
- SQLite application database with FTS5 full-text search.
- FastAPI backend and a vanilla HTML/CSS/JS frontend.
- CSV/JSON export with tag evidence.
- Evaluation framework with per-category precision/recall/F1 and error logs.
- Docker and docker-compose deployment.
