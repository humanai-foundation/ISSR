"""
Merges a filled-in labeling_batch.csv into training-ready candidate data,
in the same shape scripts/test_crossencoder_reranker.py already consumes
(foa_id, concept_id, category, label, context_snippet, is_gold).

Validates every filled row's relevant_yes_no value and every concept_id
against the live ontology before writing anything. Rows left blank are
silently skipped (partial completion is expected) rather than treated as
"no" -- an unanswered row is not evidence of irrelevance.
"""

import csv
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, "src")

from foa_pipeline.config import get_config  # noqa: E402

IN_PATH = "data/evaluation/labeling_batch.csv"
OUT_PATH = "data/evaluation/labeled_candidates.json"


def main():
    config = get_config()
    con = sqlite3.connect(config.app_db_path)
    cur = con.cursor()
    cur.execute("SELECT concept_id FROM ontology_concepts")
    valid_ids = {row[0] for row in cur.fetchall()}

    rows = list(csv.DictReader(open(IN_PATH)))
    labeled = []
    errors = []
    skipped_blank = 0

    for row in rows:
        answer = row["relevant_yes_no"].strip().lower()
        if not answer:
            skipped_blank += 1
            continue
        if answer not in ("yes", "no", "y", "n"):
            errors.append(f"row {row['row_id']}: unrecognised answer {answer!r} (use yes/no)")
            continue
        if row["concept_id"] not in valid_ids:
            errors.append(f"row {row['row_id']}: unknown concept_id {row['concept_id']!r}")
            continue

        labeled.append({
            "foa_id": row["foa_id"],
            "concept_id": row["concept_id"],
            "category": row["category"],
            "label": row["concept_label"],
            "context_snippet": row["text_snippet"],
            "is_gold": answer in ("yes", "y"),
        })

    if errors:
        print(f"{len(errors)} problem row(s) -- fix and re-run:")
        for e in errors[:20]:
            print(f"  - {e}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        return

    n_pos = sum(1 for r in labeled if r["is_gold"])
    n_method = sum(1 for r in labeled if r["category"] == "method")
    n_pop = sum(1 for r in labeled if r["category"] == "population")
    print(f"Merged {len(labeled)} labeled rows ({skipped_blank} left blank, skipped).")
    print(f"  method: {n_method} labeled, population: {n_pop} labeled")
    print(f"  positives (yes): {n_pos} total")

    Path(OUT_PATH).write_text(json.dumps(labeled, indent=2))
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
