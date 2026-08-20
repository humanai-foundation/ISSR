"""
Experiment: fine-tune a small SetFit binary relevance classifier ("does this
concept apply to this text?") on the gold set's own true/false positives, and
evaluate via FOA-level k-fold cross-validation -- never train and test on
candidates from the same FOA, or this leaks exactly the way the project's
existing gold/silver separation exists to prevent.

Input per candidate: "CONCEPT: {label}\nTEXT: {context_snippet}"
Label: 1 if this (FOA, concept) pair is a real gold tag, else 0.

Reports the SAME micro-averaged P/R/F1 methodology as evaluate --gold (sum
TP/FP/FN across all folds first, then compute once) so this is directly
comparable to current production numbers.
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, "src")

from datasets import Dataset  # noqa: E402
from setfit import SetFitModel, Trainer, TrainingArguments  # noqa: E402

CANDIDATES_PATH = "data/evaluation/setfit_candidates.json"
N_FOLDS = 5
SEED = 42
BASE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # small/fast for CV


def build_text(c):
    return f"CONCEPT: {c['label']}\nTEXT: {c['context_snippet']}"


def prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def run_category(candidates, category):
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
        train = [c for c in cat_candidates if c["foa_id"] not in test_foas]
        test = [c for c in cat_candidates if c["foa_id"] in test_foas]

        n_pos = sum(1 for c in train if c["is_gold"])
        if n_pos < 2:
            print(f"  fold {fold_idx}: skipping, only {n_pos} positive training examples")
            continue

        # Positives are ~2% of candidates -- SetFit's default classification
        # head has no imbalance correction and collapses to "always negative"
        # at that rate (measured: F1=0.000 on both categories, 0-2 positive
        # predictions total across every fold). Oversample positives to ~20%
        # of the head-training set, a standard correction for this severity
        # of imbalance -- affects both contrastive pair sampling and the
        # classification head fit, not just the head.
        positives = [c for c in train if c["is_gold"]]
        negatives = [c for c in train if not c["is_gold"]]
        target_pos_count = max(len(positives), int(0.2 * len(negatives) / 0.8))
        oversampled_positives = (positives * (target_pos_count // max(len(positives), 1) + 1))[:target_pos_count]
        train_balanced = negatives + oversampled_positives
        rng.shuffle(train_balanced)

        train_ds = Dataset.from_dict({
            "text": [build_text(c) for c in train_balanced],
            "label": [int(c["is_gold"]) for c in train_balanced],
        })

        model = SetFitModel.from_pretrained(BASE_MODEL)
        trainer = Trainer(
            model=model,
            train_dataset=train_ds,
            args=TrainingArguments(num_epochs=1, batch_size=16, num_iterations=10),
        )
        trainer.train()

        test_texts = [build_text(c) for c in test]
        preds = model.predict(test_texts)

        tp = fp = fn = 0
        for c, pred in zip(test, preds):
            pred_bool = bool(int(pred))
            if pred_bool and c["is_gold"]:
                tp += 1
            elif pred_bool and not c["is_gold"]:
                fp += 1
            elif not pred_bool and c["is_gold"]:
                fn += 1
        total_tp += tp
        total_fp += fp
        total_fn += fn
        print(f"  fold {fold_idx} ({len(test_foas)} FOAs, {len(test)} candidates): "
              f"TP={tp} FP={fp} FN={fn}")

    p, r, f1 = prf(total_tp, total_fp, total_fn)
    print(f"\n{category}: P={p:.3f} R={r:.3f} F1={f1:.3f} "
          f"(TP={total_tp} FP={total_fp} FN={total_fn}, {n_gold} gold total)")
    return {"category": category, "precision": p, "recall": r, "f1": f1,
            "tp": total_tp, "fp": total_fp, "fn": total_fn}


def main():
    candidates = json.loads(Path(CANDIDATES_PATH).read_text())
    results = []
    for category in ("method", "population"):
        print(f"=== {category} ===")
        results.append(run_category(candidates, category))
        print()
    Path("data/evaluation/setfit_cv_results.json").write_text(json.dumps(results, indent=2))


def diagnose_first_fold(candidates, category):
    """One-shot check: did the model learn any separating signal at all, or
    is the representation itself uninformative for this task? Distinguishes
    "needs threshold calibration" from "genuinely doesn't work" before
    deciding whether more tuning is justified."""
    cat_candidates = [c for c in candidates if c["category"] == category]
    foa_ids = sorted(set(c["foa_id"] for c in cat_candidates))
    rng = random.Random(SEED)
    rng.shuffle(foa_ids)
    test_foas = set(foa_ids[:4])

    train = [c for c in cat_candidates if c["foa_id"] not in test_foas]
    test = [c for c in cat_candidates if c["foa_id"] in test_foas]

    positives = [c for c in train if c["is_gold"]]
    negatives = [c for c in train if not c["is_gold"]]
    target_pos_count = max(len(positives), int(0.2 * len(negatives) / 0.8))
    oversampled = (positives * (target_pos_count // max(len(positives), 1) + 1))[:target_pos_count]
    train_balanced = negatives + oversampled
    rng.shuffle(train_balanced)

    train_ds = Dataset.from_dict({
        "text": [build_text(c) for c in train_balanced],
        "label": [int(c["is_gold"]) for c in train_balanced],
    })
    model = SetFitModel.from_pretrained(BASE_MODEL)
    trainer = Trainer(model=model, train_dataset=train_ds,
                       args=TrainingArguments(num_epochs=1, batch_size=16, num_iterations=10))
    trainer.train()

    test_texts = [build_text(c) for c in test]
    probs = model.predict_proba(test_texts)
    pos_probs = [float(p[1]) for p, c in zip(probs, test) if c["is_gold"]]
    neg_probs = [float(p[1]) for p, c in zip(probs, test) if not c["is_gold"]]
    print(f"\n[DIAGNOSIS {category}] gold-positive mean P(relevant)={sum(pos_probs)/len(pos_probs):.4f} "
          f"(n={len(pos_probs)}, values={[round(x,3) for x in pos_probs]})")
    print(f"[DIAGNOSIS {category}] non-gold mean P(relevant)={sum(neg_probs)/len(neg_probs):.4f} (n={len(neg_probs)})")


if __name__ == "__main__":
    if "--diagnose" in sys.argv:
        candidates = json.loads(Path(CANDIDATES_PATH).read_text())
        for category in ("method", "population"):
            diagnose_first_fold(candidates, category)
    else:
        main()
