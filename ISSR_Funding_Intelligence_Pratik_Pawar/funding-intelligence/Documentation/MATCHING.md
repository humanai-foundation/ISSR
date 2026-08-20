# FOA Semantic Matching (Phase 4)

This document describes how the semantic tagging outputs and the FAISS vector index are combined to match researcher abstracts to Funding Opportunity Announcements (FOAs).

> **Implemented in `src/foa_pipeline/matching/matcher.py`, exposed via CLI and API.**
>
> ```bash
> PYTHONPATH=src python -m foa_pipeline.cli search --profile "computational social science, housing policy" --k 10
> ```
> ```bash
> curl -X POST localhost:8000/api/match -H "Content-Type: application/json" \
>   -d '{"profile_text": "computational social science, housing policy", "k": 10}'
> ```
>
> Requires the FAISS index to exist — run `tag-all` first to build it.

## The Hybrid Relevance Score Formula

To ensure researchers see the most relevant grants, matching should not rely solely on dense vector search (which can hallucinate abstract conceptual links) nor solely on explicit ontology tags (which can miss nuanced language). 

We recommend using a **Hybrid Relevance Score** combining both approaches:

```
Hybrid_Score = (0.7 * Cosine_Similarity) + (0.3 * Tag_Overlap_Ratio)
```

### 1. Cosine Similarity (Dense Vectors)
Query the `data/embeddings/foa_index.faiss` index with the researcher's embedded abstract. This yields a raw cosine similarity score for the FOA document.

### 2. Tag Overlap Ratio (Explicit Ontology)
Extract ontology tags from the researcher's profile/abstract using the `foa_pipeline` tagging engine (the same L1+L2+L3 cascade used on FOAs), then compute the overlap against the FOA's stored tags.

The implementation uses the **containment ratio** — `|profile ∩ foa| / |profile|` — rather than full Jaccard. A broad FOA that carries many extra tags should not be penalised for covering everything the researcher actually asked for; Jaccard would divide by the union and punish exactly the well-matched, wide-scope opportunities a research officer wants to see.

### Implementation Example
If a researcher is looking for "Machine Learning for Veterans Health":
- The FAISS index captures the general theme (Cosine_Sim = 0.82)
- The FOA is explicitly tagged with `Populations: Veterans` and `Methods: Machine Learning`. If the researcher's profile has 4 tags and matches these 2, `Tag_Overlap_Ratio = 2/4 = 0.5`.

`Hybrid_Score = (0.7 * 0.82) + (0.3 * 0.5) = 0.574 + 0.15 = 0.724`

Recommendations to ISSR Research Development Officers are sorted by this `Hybrid_Score`.

## Implementation Notes

- **Candidate pool.** FAISS is queried for `3 × k` candidates before re-ranking. Retrieving only `k` by cosine would make the tag-overlap term decorative — an FOA ranked `k+1` by vector similarity could never be promoted into the final list no matter how well its tags matched.
- **Explainability.** Every result carries `cosine_score`, `tag_overlap_ratio`, `matched_tags` (human-readable labels), and the combined `hybrid_score`, so a ranking can be justified to a user rather than presented as an opaque number — consistent with the tag-provenance design in `ONTOLOGY.md` §5.
- **Graceful degradation.** If the tagger is unavailable or fails to tag the profile, matching falls back to cosine-only ranking (`tag_overlap_ratio = 0.0`) instead of erroring, per the fallback strategy in the blueprint's risk register.
- **Weights** are module constants (`COSINE_WEIGHT`, `TAG_WEIGHT`) and overridable per call, so the 0.7/0.3 split can be re-tuned once real user-relevance feedback exists. The current split is the blueprint's proposed default and has **not** been empirically validated against human relevance judgements — doing so is future work.

## LLM Match Explanations

**Implemented in `src/foa_pipeline/matching/explain.py`, wired into `POST /api/match` via `explain: true` (the default).**

The hybrid score is a good ranking signal but not a good sentence: "hybrid_score 0.31" tells a research development officer nothing about *why*. The top `MATCH_EXPLAIN_TOP_K` results (default 5) are sent to the local LLM (same Ollama/Mistral used for tag disambiguation in `layer3_llm.py`) with the profile text, the FOA excerpt, the matched tags, and both component scores, and asked for one grounded sentence plus a coarse relevance tier — `strong` / `moderate` / `weak`.

**The window can reorder itself, but cannot expand.** After scoring, the reviewed window is stably re-sorted by relevance tier (hybrid_score breaks ties). A candidate the LLM never saw — because it fell outside `explain_top_k` — can never be promoted above one it did review. This bounds both the LLM's influence and the request's worst-case latency to a fixed number of Ollama calls, regardless of `k`.

**Every failure mode degrades to a deterministic sentence, never an error.** Ollama unreachable, a timeout, a malformed response, an empty explanation, an unparseable relevance value — each falls back to a templated sentence built from the scores alone (`_fallback_explanation`), and the response carries `llm_available: false` so a caller can be honest with the end user about degraded mode rather than silently presenting a worse ranking as if nothing had changed.

**Measured latency (local Mistral-7B-instruct, Apple Silicon, MPS backend): ~8 seconds per explanation.** At the default `explain_top_k=5` that is 30–45 seconds per match request — real, and worth knowing before raising the default. `MATCH_EXPLAIN_TOP_K` is an environment variable specifically so a deployment can trade explanation coverage for latency without a code change.

**A pre-existing bug this surfaced, not one it introduced:** `match_profile_to_foas` never forwarded its `db` argument into `vector_index.search()`. This worked by accident from the CLI, which always constructs a `VectorIndex` with a database bound at construction — but the API's cached, cross-request index (`api/deps.py`, `db=None` by design; see its docstring) has no database of its own, so every API-driven match request raised. No unit test caught it, because every test double for `VectorIndex.search()` accepted whatever arguments it was given rather than validating the real class's contract; only running the actual server against actual data did. Now fixed (`matcher.py` passes `db=db` through), and both `test_grant_matcher.py` and `test_api.py` carry a regression test asserting the forwarding happens.

**A second pre-existing bug this surfaced:** the "Semantic Match" UI's similarity-threshold slider defaulted to 0.50 — inherited by the new endpoint's frontend wiring — but real cosine scores between a short profile and an FOA's full text commonly top out around 0.30–0.35 for genuinely relevant results (the same compressed-similarity phenomenon documented for tag-concept cosines in `EVALUATION.md`). At the old default, a realistic query could return **zero results with no explanation why**, and this reproduces identically on the pre-existing `/api/search/semantic` endpoint — it is not new to `/api/match`. The frontend default is now 0 (no pre-filter); relevance is communicated instead by the LLM tier and the hybrid score, which degrade gracefully rather than silently vanishing. The slider remains available for a user who wants a stricter cut.
