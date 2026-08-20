"""
One-off script: sample 20 candidate FOAs to expand eval_set_gold.json from
20 -> 40, correcting its current near-total NSF bias (19/20 NSF, 1 DOE-GFO)
against a corpus that has since broadened to ~1,810 FOAs across ~180
agencies, where NSF is now only ~16%.

Not part of the pipeline -- run once, review the output, hand-annotate it,
then merge into eval_set_gold.json. Safe to delete after use.
"""

import json
import random
import sqlite3
from pathlib import Path

DB_PATH = "data/db/funding_intelligence.db"
GOLD_PATH = "data/evaluation/eval_set_gold.json"
SILVER_PATH = "data/evaluation/eval_set_50.json"
OUT_PATH = "data/evaluation/gold_expansion_candidates.json"
MIN_DESCRIPTION_CHARS = 500
SEED = 42

# The existing 20-FOA gold set is already 19/20 NSF -- that's a fixed floor
# of 47.5% NSF in the combined 40 before this batch adds a single FOA. So
# priority-but-not-imbalanced can only be achieved by *this* batch skewing
# hard away from NSF (just 1 new pick, chosen to cover a directorate the
# original 19 under-represent) and toward real coverage of the rest of the
# now-1,810-FOA, ~180-agency corpus. HHS-NIH11 gets real depth (it's 38% of
# the corpus, not just a token slot) without approaching its true
# proportional share. The remaining slots are a deliberate diversity tail of
# agencies structurally unlike NSF -- foreign assistance, conservation,
# veterans health, criminal justice -- to test whether the current ontology
# (SDGs, GREAT Act, NSF directorates, academic research methods) means
# anything outside NSF-style research FOAs.
AGENCY_QUOTAS = {
    "NSF": 1,                  # original 19 already dominate; one fresh pick only
    "HHS-NIH11": 6,             # 38% of the corpus deserves real depth
    "DOD-AMRAA": 2,
    "HHS-FDA": 2,
    "HHS-CDC-HHSCDCERA": 1,
    "HHS-HRSA": 2,
    "DOS-DRL": 1,                # foreign assistance / democracy & human rights
    "DOI-FWS": 1,                 # conservation / environment
    "USDA-NIFA": 1,                # agricultural research -- NSF-adjacent, good control
    "VA-HPGPDP": 1,                 # veterans health services
    "NASA-HQ": 1,                    # aerospace research
    "USDOJ-OJP-BJA": 1,               # criminal justice program grants
}
assert sum(AGENCY_QUOTAS.values()) == 20
# Full 40-FOA composition this produces: NSF 20/40 (50%) -- still clearly
# largest, down from 95% -- HHS-NIH11 6/40 (15%), everyone else 1-2 each.


def main() -> None:
    existing_ids = {e["foa_id"] for e in json.loads(Path(GOLD_PATH).read_text())}
    if Path(SILVER_PATH).exists():
        existing_ids |= {e["foa_id"] for e in json.loads(Path(SILVER_PATH).read_text())}

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    rng = random.Random(SEED)
    candidates = []
    for agency, quota in AGENCY_QUOTAS.items():
        cur.execute(
            """
            SELECT foa_id, title, agency, agency_code, program_description,
                   eligibility_description
            FROM foa_records
            WHERE agency_code = ?
              AND length(program_description) >= ?
            """,
            (agency, MIN_DESCRIPTION_CHARS),
        )
        pool = [dict(r) for r in cur.fetchall() if r["foa_id"] not in existing_ids]
        if len(pool) < quota:
            print(f"WARNING: only {len(pool)} eligible FOAs for {agency}, wanted {quota}")
        picked = rng.sample(pool, min(quota, len(pool)))
        candidates.extend(picked)

    Path(OUT_PATH).write_text(json.dumps(candidates, indent=2))
    print(f"Wrote {len(candidates)} candidates to {OUT_PATH}")
    for c in candidates:
        print(f"  [{c['agency_code']}] {c['title'][:80]}")


if __name__ == "__main__":
    main()
