"""
Reruns the Attempt 4 cross-encoder architecture (test_crossencoder_reranker.py)
against real human-labeled data instead of the 20-gold-FOA-derived
setfit_candidates.json.

The original attempt was architecturally correct but data-starved: ~9
positive examples per training fold (11-19 positives total, drawn from only
20 gold FOAs), which Documentation/EVALUATION.md 4k diagnosed as "right architecture,
insufficient data." data/evaluation/labeled_candidates.json (from
labeling_batch.csv, human-judged) supplies 44 method positives / 175 FOAs
and 72 population positives / 168 FOAs -- still short of the ~80-100/category
target stated in LABELING_INSTRUCTIONS.md, but a real multiple of what the
prior attempt trained on. Everything else (model, loss, CV structure,
threshold-picking discipline) is identical to the original attempt so the
two results are directly comparable.
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

CANDIDATES_PATH = "data/evaluation/labeled_candidates.json"
N_FOLDS = 5
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
              f"fit_pos={n_pos}, threshold={threshold:.3f}): TP={tp} FP={fp} FN={fn}")

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
    Path("data/evaluation/crossencoder_human_labels_cv_results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
