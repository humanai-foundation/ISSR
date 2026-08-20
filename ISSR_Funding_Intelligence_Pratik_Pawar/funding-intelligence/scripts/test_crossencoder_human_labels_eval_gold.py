"""
The apples-to-apples version of test_crossencoder_human_labels.py.

That script's CV numbers (method F1 0.390, population F1 0.380) are scored
against held-out slices of the labeling_batch pool itself -- a deliberately
harder, gray-zone candidate set from 300 different, non-gold FOAs. They are
NOT comparable to the "current production" F1 (0.480 method, 0.522
population) quoted throughout Documentation/EVALUATION.md, since that number is always
scored against the fixed 20-gold-FOA candidate pool in
data/evaluation/setfit_candidates.json.

This script closes that gap correctly: train ONCE on all 1083 human-labeled
candidates (data/evaluation/labeled_candidates.json, drawn from 300 FOAs
that generate_labeling_batch.py explicitly excluded the gold set and its
expansion candidates from -- see its `excluded = gold_ids | cand_ids`), then
evaluate that single trained model directly against setfit_candidates.json
(the 20 gold FOAs' real L2 candidates, TP/FP-labeled). No FOA overlap
between train and eval, so this is a clean held-out test and the resulting
F1 is directly comparable to the 0.480/0.522 production numbers quoted
everywhere else in Documentation/EVALUATION.md's §4k.

Threshold is picked on a held-out 20% slice of the *training* FOAs (never
touching setfit_candidates.json), same discipline as every other threshold
in this project's reranking experiments.
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

TRAIN_PATH = "data/evaluation/labeled_candidates.json"
EVAL_PATH = "data/evaluation/setfit_candidates.json"
SEED = 42
BASE_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
VAL_FRACTION = 0.2


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


def train_model(train_candidates, descriptions):
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


def score(model, candidates, descriptions):
    pairs = [[c["context_snippet"], build_concept_text(c["concept_id"], descriptions)] for c in candidates]
    raw_scores = model.predict(pairs, apply_softmax=False, show_progress_bar=False)
    return torch.sigmoid(torch.tensor(raw_scores)).tolist()


def pick_threshold(model, val_candidates, descriptions):
    if not any(c["is_gold"] for c in val_candidates):
        return 0.5
    scores = score(model, val_candidates, descriptions)
    best = (0.5, -1.0)
    for thresh in sorted(set(scores)):
        tp = sum(1 for s, c in zip(scores, val_candidates) if s >= thresh and c["is_gold"])
        fp = sum(1 for s, c in zip(scores, val_candidates) if s >= thresh and not c["is_gold"])
        fn = sum(1 for c in val_candidates if c["is_gold"]) - tp
        _, _, f1 = prf(tp, fp, fn)
        if f1 > best[1]:
            best = (thresh, f1)
    return best[0]


def run_category(train_all, eval_all, category, descriptions):
    train_cat = [c for c in train_all if c["category"] == category]
    eval_cat = [c for c in eval_all if c["category"] == category]

    foa_ids = sorted(set(c["foa_id"] for c in train_cat))
    rng = random.Random(SEED)
    rng.shuffle(foa_ids)
    n_val = max(1, int(len(foa_ids) * VAL_FRACTION))
    val_foas = set(foa_ids[:n_val])
    fit_foas = set(foa_ids[n_val:])

    fit_candidates = [c for c in train_cat if c["foa_id"] in fit_foas]
    val_candidates = [c for c in train_cat if c["foa_id"] in val_foas]

    n_pos_fit = sum(1 for c in fit_candidates if c["is_gold"])
    n_pos_eval = sum(1 for c in eval_cat if c["is_gold"])
    print(f"{category}: fit on {len(fit_candidates)} candidates ({n_pos_fit} positive, "
          f"{len(fit_foas)} FOAs), threshold picked on {len(val_candidates)} held-out "
          f"training candidates, evaluated on {len(eval_cat)} gold-FOA candidates "
          f"({n_pos_eval} positive)")

    model = train_model(fit_candidates, descriptions)
    threshold = pick_threshold(model, val_candidates, descriptions)

    eval_scores = score(model, eval_cat, descriptions)
    tp = fp = fn = 0
    for s, c in zip(eval_scores, eval_cat):
        pred = s >= threshold
        if pred and c["is_gold"]:
            tp += 1
        elif pred and not c["is_gold"]:
            fp += 1
        elif not pred and c["is_gold"]:
            fn += 1

    p, r, f1 = prf(tp, fp, fn)
    print(f"  threshold={threshold:.3f}  P={p:.3f} R={r:.3f} F1={f1:.3f} "
          f"(TP={tp} FP={fp} FN={fn})\n")
    return {"category": category, "threshold": threshold, "precision": p, "recall": r,
            "f1": f1, "tp": tp, "fp": fp, "fn": fn, "n_train": len(fit_candidates),
            "n_train_pos": n_pos_fit, "n_eval": len(eval_cat), "n_eval_pos": n_pos_eval}


def main():
    train_all = json.loads(Path(TRAIN_PATH).read_text())
    eval_all = json.loads(Path(EVAL_PATH).read_text())
    descriptions = load_descriptions()

    train_foas = {c["foa_id"] for c in train_all}
    eval_foas = {c["foa_id"] for c in eval_all}
    overlap = train_foas & eval_foas
    if overlap:
        print(f"WARNING: {len(overlap)} FOAs overlap between train and eval sets -- results invalid")
        return
    print(f"No FOA overlap confirmed ({len(train_foas)} train FOAs, {len(eval_foas)} eval FOAs)\n")

    results = []
    for category in ("method", "population"):
        results.append(run_category(train_all, eval_all, category, descriptions))
    Path("data/evaluation/crossencoder_human_labels_eval_gold_results.json").write_text(
        json.dumps(results, indent=2)
    )


if __name__ == "__main__":
    main()
