"""
Turns data/evaluation/gold_expansion_candidates.json into a human-fillable
markdown packet. Fill in TAGS: and RATIONALE: for each FOA, then run
merge_annotation_packet.py to append the results to eval_set_gold.json.

Tag against Documentation/ONTOLOGY.md's concept IDs (great_XX, sdg_XX, method_XX, pop_XX,
nsf_XX). Follow Documentation/ANNOTATION_CODEBOOK.md: a concept applies only if it's a
primary focus of the FOA, not merely mentioned in passing.
"""

import json
from pathlib import Path

IN_PATH = "data/evaluation/gold_expansion_candidates.json"
OUT_PATH = "data/evaluation/gold_expansion_annotation_packet.md"


def main() -> None:
    candidates = json.loads(Path(IN_PATH).read_text())
    lines = [
        "# Gold Set Expansion — Annotation Packet",
        "",
        f"{len(candidates)} FOAs to bring `eval_set_gold.json` from 20 -> 40.",
        "Fill in `TAGS:` (comma-separated concept IDs from Documentation/ONTOLOGY.md) and",
        "`RATIONALE:` for each entry below, then run",
        "`scripts/merge_annotation_packet.py`.",
        "",
        "Primary focus only (Documentation/ANNOTATION_CODEBOOK.md) — don't tag something",
        "just because the word appears once in passing.",
        "",
        "---",
        "",
    ]
    for i, c in enumerate(candidates, 1):
        lines += [
            f"## [{i}/{len(candidates)}] {c['agency_code']} — {c['title']}",
            f"FOA_ID: {c['foa_id']}",
            "",
            "### Program Description",
            c["program_description"] or "(none)",
            "",
            "### Eligibility Description",
            c["eligibility_description"] or "(none)",
            "",
            "TAGS: ",
            "RATIONALE: ",
            "",
            "---",
            "",
        ]
    Path(OUT_PATH).write_text("\n".join(lines))
    print(f"Wrote packet for {len(candidates)} FOAs to {OUT_PATH}")


if __name__ == "__main__":
    main()
