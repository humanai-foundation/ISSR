<!--
Thanks for contributing. Keep the PR focused — a bug fix and a refactor
belong in separate PRs. See CONTRIBUTING.md.
-->

## What does this change?

<!-- What changed and, more importantly, why. Future maintainers read PR
history to understand decisions, so record the reasoning, not just the diff. -->

## Related issue

<!-- e.g. Closes #12 -->

---

## Checklist

- [ ] `make test` passes (note: 3 failures in `tests/test_tagger_l1.py` are pre-existing)
- [ ] `make lint` passes
- [ ] New/changed public functions have type hints
- [ ] New public names are exported from their subpackage `__init__.py`, and I confirmed they resolve

## Does this touch the tagging engine?

<!-- Delete this section if not. Otherwise it is required — see CONTRIBUTING.md. -->

Changes to synonyms, the ontology, thresholds, or any tagging layer need
before/after gold-standard numbers:

```bash
PYTHONPATH=src python -m foa_pipeline.cli setup-ontology        # if synonyms/ontology changed
PYTHONPATH=src python -m foa_pipeline.cli precompute-embeddings # if concept descriptions changed
PYTHONPATH=src python -m foa_pipeline.cli tag-all
PYTHONPATH=src python -m foa_pipeline.cli evaluate --gold
```

| Metric | Before | After |
|---|---|---|
| Precision | | |
| Recall | | |
| F1 | | |

Per-category movement (note any category that regressed):

<!-- If global F1 drops, say why the change is still worth keeping. Metrics
must come from the hand-labelled gold set, never from eval_set_50.json —
that is an LLM-generated silver set and scoring against it is circular. -->

## Anything reviewers should look at closely?

<!-- Trade-offs, things you were unsure about, or areas you'd like a second
opinion on. Flagging uncertainty is helpful, not a weakness. -->
