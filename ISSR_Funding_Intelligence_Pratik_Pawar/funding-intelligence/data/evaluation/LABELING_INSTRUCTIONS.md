# Labeling Instructions — `labeling_batch.csv`

## What this is

Not full gold-standard annotation. **One fast yes/no judgment per row** —
does this specific concept genuinely apply to this specific grant, based on
this snippet.

**1,090 rows: 440 `method`, 650 `population`.** This is meant to get the
cross-encoder reranker (see `Documentation/EVALUATION.md` §4k, "Attempt 4") past the
data-volume wall it hit — it showed a real but too-weak-and-noisy signal on
~9 positive examples per training fold, and needs roughly 80-100 real
positives per category to have a realistic shot. Based on this batch's
threshold, expect maybe 20-30% of rows to come back "yes" — so this batch is
sized to land in that range, not because every row needs to be relevant.

**Partial completion is genuinely fine.** Send back however much you finish
— more data always helps, but there's no all-or-nothing cutoff. If you want
to prioritize one category, `method` is the smaller batch (440 rows).

## How to fill it in

Open `labeling_batch.csv` in Excel, Google Sheets, or Numbers. For each row,
put **`yes`** or **`no`** in the `relevant_yes_no` column based on:

- **`title`** — the FOA's title, for orientation
- **`concept_label`** / **`concept_description`** — what the candidate
  concept actually means (read this, not just the label — several concepts
  are easy to misjudge from the label alone, e.g. "Citizen Science" has a
  specific meaning that excludes general public outreach)
- **`text_snippet`** — the actual passage from the grant text that triggered
  this candidate

**The rule** (same principle as `Documentation/ANNOTATION_CODEBOOK.md`): answer **yes**
only if the concept is a **primary focus** of what's described in the
snippet — not merely mentioned, adjacent, or an example among several. If
"machine learning" appears as one of many optional approaches a proposer
*could* take, that's `no`. If the program explicitly requires or centers on
it, that's `yes`.

**Judge from the snippet alone, not the full FOA.** This is deliberate, not
a shortcut — the model being trained will only ever see this snippet, so a
label based on context the snippet doesn't contain wouldn't reflect what's
actually learnable from it. If the snippet genuinely isn't enough to judge,
leave it blank rather than guessing from the title.

**Same `foa_id` appears multiple times** — once per candidate concept for
that FOA. That's expected; each row is an independent judgment about one
concept, not about the FOA as a whole.

## What NOT to do

- Don't try to look up the FOA elsewhere or read the full description —
  snippet-only is the point (see above).
- Don't skip around trying to "balance" yes/no counts — judge each row on
  its own merits. An uneven split is expected and fine.
- Don't worry about the concepts you don't see — this batch only covers
  `method` and `population`; the other three categories aren't part of this
  batch.

## When you're done

Send the file back (however much is filled in) and I'll validate the
concept IDs, merge it into training data, and retrain. If it's a lot of
rows, doing it in a few sessions rather than one sitting is completely fine
— just save and re-send whenever you stop.
