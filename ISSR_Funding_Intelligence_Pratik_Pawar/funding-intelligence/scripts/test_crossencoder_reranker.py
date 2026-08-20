"""
The real pairwise cross-encoder attempt (see Documentation/EVALUATION.md 4k for why the
prior two -- zero-shot NLI, SetFit's binary reformulation -- both failed and
what a correctly-shaped attempt needs to fix).

Fixes relative to both prior attempts:
  - Genuine pairwise architecture: CrossEncoder(num_labels=1) jointly scores
    (snippet, concept) pairs directly via BCEWithLogitsLoss on the real
    labels -- no same-class contrastive assumption to break (that was
    SetFit's failure mode), and no reliance on a model's zero-shot NLI
    training distribution (that was attempt 1's failure mode).
  - Starts from cross-encoder/ms-marco-MiniLM-L-6-v2, a model already
    pretrained for "is this passage relevant to this query" -- much closer
    to our actual task than a plain LM or an NLI-only model, which matters
    enormously when the fine-tuning set is this small.
  - Class imbalance handled via BCEWithLogitsLoss's pos_weight (principled
    reweighting), not oversampling/duplication.
  - Concept side uses the full ontology description, not just the label --
    this project's own history (4c, 4f) found description richness matters
    a lot for embedding-based concept matching.

FOA-level 5-fold CV, same seed and fold structure as the SetFit attempt for
direct comparability. Threshold picked on a held-out slice of each fold's
TRAINING FOAs (never the test fold), so the reported number isn't
threshold-tuned against the same data it's evaluated on.
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, "src")

import torch  # noqa: E402
from sentence_transformers import CrossEncoder, InputExample  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402

from foa_pipeline.config import get_config  # noqa: E402
from foa_pipeline.ontology.store import OntologyStore  # noqa: E402

CANDIDATES_PATH = "data/evaluation/setfit_candidates.json"
N_FOLDS = 5
SEED = 42
BASE_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
VAL_FRACTION = 0.2  # of training FOAs, held out within the fold to pick a threshold


def load_descriptions():
    config = get_config()
    store = OntologyStore(config.app_db_path)
    cur = store.conn.cursor()
    cur.execute("SELECT concept_id, label, description FROM ontology_concepts")
    return {row["concept_id"]: (row["label"], row["description"] or "") for row in cur.fetchall()}


def build_concept_text(concept_id, descriptions):
    label, desc = descriptions.get(concept_id, (concept_id, ""))
    return f"{label}: {desc}" if desc else label


def prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def train_fold(train_candidates, descriptions):
    n_pos = sum(1 for c in train_candidates if c["is_gold"])
    n_neg = len(train_candidates) - n_pos

    examples = [
        InputExample(
            texts=[c["context_snippet"], build_concept_text(c["concept_id"], descriptions)],
            label=float(c["is_gold"]),
        )
        for c in train_candidates
    ]
    loader = DataLoader(examples, shuffle=True, batch_size=16)

    model = CrossEncoder(BASE_MODEL, num_labels=1)
    # fit() moves the model to model._target_device (MPS on this machine) --
    # pos_weight has to live on the same device or BCEWithLogitsLoss's
    # internal matmul fails with a device-mismatch error at the first batch.
    pos_weight = torch.tensor([n_neg / max(n_pos, 1)], device=model._target_device)
    loss_fct = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    model.fit(
        train_dataloader=loader,
        epochs=3,
        loss_fct=loss_fct,
        show_progress_bar=False,
        warmup_steps=10,
        save_best_model=False,
    )
    return model


def pick_threshold(model, val_candidates, descriptions):
    """Sweep thresholds on held-out (from training FOAs, not the test fold)
    candidates; return the F1-best cutoff. Falls back to 0.5 if val set has
    no positives to optimise against."""
    if not any(c["is_gold"] for c in val_candidates):
        return 0.5
    pairs = [[c["context_snippet"], build_concept_text(c["concept_id"], descriptions)] for c in val_candidates]
    raw_scores = model.predict(pairs, apply_softmax=False, show_progress_bar=False)
    scores = torch.sigmoid(torch.tensor(raw_scores)).tolist()

    best = (0.5, -1.0)
    for thresh in sorted(set(scores)):
        tp = sum(1 for s, c in zip(scores, val_candidates) if s >= thresh and c["is_gold"])
        fp = sum(1 for s, c in zip(scores, val_candidates) if s >= thresh and not c["is_gold"])
        fn = sum(1 for c in val_candidates if c["is_gold"]) - tp
        _, _, f1 = prf(tp, fp, fn)
        if f1 > best[1]:
            best = (thresh, f1)
    return best[0]


def run_category(candidates, category, descriptions):
    cat_candidates = [c for c in candidates if c["category"] == category]
    foa_ids = sorted(set(c["foa_id"] for c in cat_candidates))
    rng = random.Random(SEED)
    rng.shuffle(foa_ids)

    fold_size = max(1, len(foa_ids) // N_FOLDS)
    folds = [foa_ids[i : i + fold_size] for i in range(0, len(foa_ids), fold_size)]

    total_tp = total_fp = total_fn = 0
    n_gold = sum(1 for c in cat_candidates if c["is_gold"])

    for fold_idx, test_foas in enumerate(folds):
        test_foas = set(test_foas)
        train_foas = [f for f in foa_ids if f not in test_foas]
        n_val_foas = max(1, int(len(train_foas) * VAL_FRACTION))
        val_foas = set(train_foas[:n_val_foas])
        fit_foas = set(train_foas[n_val_foas:])

        fit_candidates = [c for c in cat_candidates if c["foa_id"] in fit_foas]
        val_candidates = [c for c in cat_candidates if c["foa_id"] in val_foas]
        test_candidates = [c for c in cat_candidates if c["foa_id"] in test_foas]

        n_pos = sum(1 for c in fit_candidates if c["is_gold"])
        if n_pos < 2:
            print(f"  fold {fold_idx}: skipping, only {n_pos} positive fit examples")
            continue

        model = train_fold(fit_candidates, descriptions)
        threshold = pick_threshold(model, val_candidates, descriptions)

        pairs = [[c["context_snippet"], build_concept_text(c["concept_id"], descriptions)] for c in test_candidates]
        raw_scores = model.predict(pairs, apply_softmax=False, show_progress_bar=False)
        scores = torch.sigmoid(torch.tensor(raw_scores)).tolist()

        tp = fp = fn = 0
        for s, c in zip(scores, test_candidates):
            pred = s >= threshold
            if pred and c["is_gold"]:
                tp += 1
            elif pred and not c["is_gold"]:
                fp += 1
            elif not pred and c["is_gold"]:
                fn += 1
        total_tp += tp
        total_fp += fp
        total_fn += fn
        print(f"  fold {fold_idx} ({len(test_foas)} FOAs, {len(test_candidates)} candidates, "
              f"threshold={threshold:.3f}): TP={tp} FP={fp} FN={fn}")

    p, r, f1 = prf(total_tp, total_fp, total_fn)
    print(f"\n{category}: P={p:.3f} R={r:.3f} F1={f1:.3f} "
          f"(TP={total_tp} FP={total_fp} FN={total_fn}, {n_gold} gold total)")
    return {"category": category, "precision": p, "recall": r, "f1": f1,
            "tp": total_tp, "fp": total_fp, "fn": total_fn}


def main():
    candidates = json.loads(Path(CANDIDATES_PATH).read_text())
    descriptions = load_descriptions()
    results = []
    for category in ("method", "population"):
        print(f"=== {category} ===")
        results.append(run_category(candidates, category, descriptions))
        print()
    Path("data/evaluation/crossencoder_cv_results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
