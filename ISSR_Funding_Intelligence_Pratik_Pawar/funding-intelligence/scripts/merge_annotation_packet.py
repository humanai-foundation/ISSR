"""
Parses the filled-in data/evaluation/gold_expansion_annotation_packet.md and
appends the results to eval_set_gold.json, taking it from 20 -> 40 entries.

Run after filling in every TAGS:/RATIONALE: line in the packet. Validates
every concept ID against the live ontology store before writing anything,
and refuses to run if any FOA is missing tags -- a partial merge would
silently leave gaps invisible until the next evaluate --gold run.
"""

import json
import re
import sqlite3
from pathlib import Path

PACKET_PATH = "data/evaluation/gold_expansion_annotation_packet.md"
GOLD_PATH = "data/evaluation/eval_set_gold.json"
DB_PATH = "data/db/funding_intelligence.db"

ENTRY_RE = re.compile(
    r"FOA_ID: (?P<foa_id>[0-9a-f-]+).*?"
    r"TAGS:\s*(?P<tags>.*?)\n"
    r"RATIONALE:\s*(?P<rationale>.*?)\n",
    re.DOTALL,
)


def load_valid_concept_ids() -> set[str]:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT concept_id FROM ontology_concepts")
    return {row[0] for row in cur.fetchall()}


def main() -> None:
    text = Path(PACKET_PATH).read_text()
    valid_ids = load_valid_concept_ids()

    entries = []
    errors = []
    for m in ENTRY_RE.finditer(text):
        foa_id = m.group("foa_id").strip()
        tags = [t.strip() for t in m.group("tags").split(",") if t.strip()]
        rationale = m.group("rationale").strip()

        if not tags:
            errors.append(f"{foa_id}: no tags filled in")
            continue
        bad_ids = [t for t in tags if t not in valid_ids]
        if bad_ids:
            errors.append(f"{foa_id}: unknown concept ID(s) {bad_ids}")
            continue
        if not rationale:
            errors.append(f"{foa_id}: no rationale filled in")
            continue

        entries.append({"foa_id": foa_id, "human_tags": tags, "rationale": rationale})

    if errors:
        print(f"Refusing to merge -- {len(errors)} problem(s):")
        for e in errors:
            print(f"  - {e}")
        return

    if len(entries) != 20:
        print(f"Expected 20 filled entries, found {len(entries)}. Aborting.")
        return

    # Pull titles back in from the DB so gold entries carry the same shape
    # as the existing 20 (foa_id, title, human_tags, rationale).
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    for e in entries:
        cur.execute("SELECT title FROM foa_records WHERE foa_id = ?", (e["foa_id"],))
        row = cur.fetchone()
        e["title"] = row[0] if row else "(title not found)"
        # Reorder to match the existing file's key order.
        e_ordered = {
            "foa_id": e["foa_id"],
            "title": e["title"],
            "human_tags": e["human_tags"],
            "rationale": e["rationale"],
        }
        e.clear()
        e.update(e_ordered)

    gold = json.loads(Path(GOLD_PATH).read_text())
    existing_ids = {g["foa_id"] for g in gold}
    dupes = [e["foa_id"] for e in entries if e["foa_id"] in existing_ids]
    if dupes:
        print(f"Refusing to merge -- already in gold set: {dupes}")
        return

    gold.extend(entries)
    Path(GOLD_PATH).write_text(json.dumps(gold, indent=2))
    print(f"Merged {len(entries)} new entries. eval_set_gold.json now has {len(gold)}.")


if __name__ == "__main__":
    main()
