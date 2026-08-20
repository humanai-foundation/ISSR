# FOA Tagging Annotation Codebook

> A guide for human annotators labeling Funding Opportunity Announcements (FOAs) against the project's ontology. Written for domain experts (e.g. ISSR research development officers) who may not be familiar with the underlying code — no software background needed to use this document.

**Codebook version:** 1.0 · **Last updated:** 2026-07-29

---

## 1. Purpose

This system automatically tags FOAs with structured labels so researchers can search and filter funding opportunities by subject, method, target population, and sponsor mission. The automated tagger's accuracy is measured against a small set of examples that a human has labeled by hand (the "gold standard" — see `EVALUATION.md`). Right now that gold standard has two limitations this annotation effort is meant to fix:

1. It was labeled by **one person**, so we can't tell how much of the labeling reflects real signal in the FOA text versus that one person's individual judgment calls.
2. It only covers **20 FOAs** — too small to draw statistically confident conclusions about where the system is weak.

If you're reading this as an annotator, your job is to independently read FOA text and assign tags from the ontology below — **without looking at any existing tags or another annotator's answers** — so we can measure genuine agreement and expand the gold standard.

---

## 2. General Annotation Principles

Read these before you start; they apply across every category.

1. **Read the full text before tagging.** Use the FOA's title, program description, and eligibility description together. Don't tag based on the title alone.
2. **Tag only the primary focus, not passing mentions.** A tag should apply if a category is a *central subject* of the funding opportunity — not just a word that happens to appear. Example: an FOA about ocean chemistry that briefly notes "findings may inform climate policy" should probably **not** get a Climate Action tag unless climate is actually a stated objective, not an aside.
3. **It's fine to assign zero, one, or several tags per category.** There's no minimum or required count. Many FOAs will have no Method or Population tag at all — that's a correct, valid answer, not a gap you need to fill.
4. **"Required" vs. "merely mentioned" matters most for the Methods category.** An FOA that lists "machine learning" as one of many illustrative examples of eligible topics is different from one that requires applicants to use a specific method. When in doubt, ask: *would a proposal using a completely different method still be competitive under this FOA?* If yes, be cautious about tagging that method.
5. **Methods can be reasonably inferred, not just literally quoted.** If an FOA is clearly about a technical area that's inseparable from a method — e.g. a robotics FOA that discusses "embodied intelligence, perception, and decision-making" — it's reasonable to tag Machine Learning / Computer Vision even without those literal words, because the science described genuinely depends on those methods. This is a judgment call; write down your reasoning (see §5) so it can be reviewed.
6. **When genuinely unsure, tag it and flag it**, rather than silently guessing. Use the "notes/confidence" field described in §5 to mark anything you're unsure about — those are exactly the cases we most want to review and discuss.

---

## 3. The Five Categories

Every concept has a short ID (e.g. `sdg_03`, `great_02`) used only for bookkeeping — refer to concepts by their plain-language label when annotating.

### 3.1 Research Domains (`research_domain`) — UN Sustainable Development Goals

**What it captures:** the broad, policy-level societal theme the research connects to.

**Include when:** the FOA's stated scientific scope directly maps to one of these themes as a stated goal, not an implied side benefit.

| ID | Label |
|---|---|
| sdg_01 | No Poverty |
| sdg_02 | Zero Hunger |
| sdg_03 | Good Health and Well-being |
| sdg_04 | Quality Education |
| sdg_05 | Gender Equality |
| sdg_06 | Clean Water and Sanitation |
| sdg_07 | Affordable and Clean Energy |
| sdg_08 | Decent Work and Economic Growth |
| sdg_09 | Industry, Innovation and Infrastructure |
| sdg_10 | Reduced Inequalities |
| sdg_11 | Sustainable Cities and Communities |
| sdg_12 | Responsible Consumption and Production |
| sdg_13 | Climate Action |
| sdg_14 | Life Below Water |
| sdg_15 | Life on Land |
| sdg_16 | Peace, Justice and Strong Institutions |
| sdg_17 | Partnerships for the Goals |

**Known difficulty:** these are policy categories, not scientific disciplines, so many legitimate FOAs (e.g. basic chemistry or math research) won't map to any SDG at all — that's expected and correct, don't force a fit.

### 3.2 Research Disciplines (`research_discipline`) — NSF Directorates

**What it captures:** which academic/scientific discipline the funding opportunity is organized under. This is usually easier and more reliable to assign than Research Domain, since it maps directly to how NSF itself organizes solicitations.

| ID | Label |
|---|---|
| nsf_bio | Biological Sciences |
| nsf_cise | Computer and Information Science and Engineering |
| nsf_edu | STEM Education |
| nsf_eng | Engineering |
| nsf_geo | Geosciences |
| nsf_mps | Mathematical and Physical Sciences |
| nsf_sbe | Social, Behavioral and Economic Sciences |
| nsf_tip | Technology Innovation and Partnerships |

**Include when:** the FOA is issued by, or clearly aligned with, that directorate's scope — often stated directly in the FOA text or evident from the issuing NSF division.

### 3.3 Methods and Approaches (`method`)

**What it captures:** research methodologies the FOA requires or clearly presupposes (see principle 4 and 5 above on "required" vs. "mentioned").

| ID | Label | ID | Label |
|---|---|---|---|
| method_01 | Machine Learning | method_14 | Field Experiment |
| method_02 | Deep Learning | method_15 | Ethnography |
| method_03 | Natural Language Processing | method_16 | Meta-Analysis |
| method_04 | Computer Vision | method_17 | Data Science |
| method_05 | Randomized Controlled Trial | method_18 | Remote Sensing |
| method_06 | Survey Research | method_19 | Bioinformatics |
| method_07 | Qualitative Research | method_20 | Clinical Trial |
| method_08 | Mixed Methods Research | method_21 | Policy Analysis |
| method_09 | Community-Based Participatory Research | method_22 | Network Analysis |
| method_10 | Longitudinal Study | method_23 | Participatory Action Research |
| method_11 | Geospatial Analysis | method_24 | Systems Thinking |
| method_12 | Statistical Modeling | method_25 | Citizen Science |
| method_13 | Simulation and Modeling | | |

**Exclude:** generic words like "research," "analysis," or "study" on their own — these apply to nearly everything and carry no useful signal.

### 3.4 Target Populations (`population`)

**What it captures:** demographic groups the FOA specifically targets or is designed to benefit — not just anyone who might read the eventual publication.

| ID | Label | ID | Label |
|---|---|---|---|
| pop_01 | Rural Communities | pop_11 | Immigrants and Refugees |
| pop_02 | Urban Communities | pop_12 | Students |
| pop_03 | Low-Income Populations | pop_13 | LGBTQ+ Populations |
| pop_04 | Children and Youth | pop_14 | Incarcerated Populations |
| pop_05 | Older Adults | pop_15 | Homeless Populations |
| pop_06 | Veterans | pop_16 | Agricultural Workers |
| pop_07 | Indigenous Peoples | pop_17 | Healthcare Workers |
| pop_08 | Racial and Ethnic Minorities | pop_18 | First Responders |
| pop_09 | Women and Girls | pop_19 | Small Business Owners |
| pop_10 | People with Disabilities | pop_20 | Tribal Communities |

**Include when:** the FOA explicitly names the group as who the research is about or who it serves. **Exclude** generic phrases like "the public" or "participants."

### 3.5 Sponsor Themes (`sponsor_theme`) — GREAT Act Mission Categories

**What it captures:** the federal government's policy/mission rationale for funding this work — *why* the government is paying for it, distinct from what the science is about.

| ID | Label |
|---|---|
| great_01 | National Defense |
| great_02 | Health |
| great_03 | Space |
| great_04 | Energy |
| great_05 | General Science |
| great_06 | Natural Resources and Environment |
| great_07 | Agriculture |
| great_08 | Transportation |
| great_09 | Education and Training |
| great_10 | International Affairs |
| great_11 | Income Security |
| great_12 | Veterans Benefits |
| great_13 | Community and Regional Development |
| great_14 | Administration of Justice |

**Note:** `great_05` (General Science) is a legitimate, common tag for basic/fundamental research FOAs that don't fit a more specific mission area — don't leave a basic-research FOA with zero sponsor theme tags just because none of the more specific categories fit.

---

## 4. Worked Examples (real FOAs, with reasoning)

These are drawn from the actual project data, with the reasoning the original annotator used — study these to calibrate your judgment before starting.

**"Foundational Research in Robotics"** (NSF, CISE + ENG directorates)
→ Tags: General Science (`great_05`); Machine Learning (`method_01`); Computer Vision (`method_04`); Computer and Information Science and Engineering (`nsf_cise`); Engineering (`nsf_eng`)
→ Reasoning: the FOA never says "machine learning" or "computer vision" literally, but it describes robots that must "process information, sense, plan, and move" — perception and intelligent decision-making are inseparable from what's being funded, so tagging the methods is a justified inference, not a stretch. This is the kind of case principle 5 (§2) is about.

**"Sociology"** (NSF, SBE directorate)
→ Tags: General Science (`great_05`); Reduced Inequalities (`sdg_10`); Survey Research (`method_06`); Field Experiment (`method_14`); Social, Behavioral and Economic Sciences (`nsf_sbe`)
→ Reasoning: the FOA mentions "original data collection" and "quantitative and qualitative methodological tools" — general enough that reasonable annotators could disagree on which specific methods apply. This is a genuinely ambiguous case — if you were annotating this one, this is exactly the kind of item to flag with a confidence note (§5).

**"Documenting Endangered Languages"** (NSF/NEH partnership)
→ Tags: General Science (`great_05`); Indigenous Peoples (`pop_07`); Field Experiment (`method_14`); Social, Behavioral and Economic Sciences (`nsf_sbe`)
→ Reasoning: "fieldwork" is stated directly in the text, a clear match for Field Experiment. Indigenous Peoples is tagged because endangered languages are disproportionately those of indigenous communities — a reasonable inference the FOA itself supports contextually, but worth a confidence flag since it's not stated outright.

**"Division of Chemistry: Disciplinary Research Programs"** (NSF, MPS directorate)
→ Tags: General Science (`great_05`); Mathematical and Physical Sciences (`nsf_mps`) — **and nothing else.**
→ Reasoning: this is a minimal, correct answer. No SDG, no method, no population applies here, and that's fine — resist the urge to find a tag for every category on every FOA.

---

## 5. Recording Your Annotations

Until a dedicated labeling tool is set up, record answers in a spreadsheet (Google Sheets or Excel) with one row per FOA and these columns:

| Column | What to put in it |
|---|---|
| `foa_id` | Provided to you — do not change |
| `title` | Provided to you — do not change |
| `research_domain_tags` | Comma-separated concept IDs (e.g. `sdg_10, sdg_13`), or blank |
| `research_discipline_tags` | Same format |
| `method_tags` | Same format |
| `population_tags` | Same format |
| `sponsor_theme_tags` | Same format |
| `confidence_flags` | Any concept ID(s) you're unsure about, plus a short reason |
| `annotator_id` | Your assigned annotator code (not your name — see §7) |
| `date` | Date you completed this FOA |

One filled-in row, using the Chemistry example above, would look like:
`nsf_mps | (blank) | (blank) | (blank) | great_05, nsf_mps | (blank) | ANNOT_1 | 2026-08-01`

---

## 6. Inter-Annotator Agreement Protocol

To make the resulting dataset statistically meaningful, this process is required, not optional:

1. **At least two annotators**, working independently — no discussing FOAs with each other until both are done with the overlap set.
2. **Full overlap on the existing 20-FOA gold set**, plus a **shared overlap of 20–30%** of any newly added FOAs (e.g. if 60 new FOAs are added, at least 12–18 should be labeled by both annotators).
3. Once both annotators finish the overlap set independently, agreement is computed per category (Cohen's kappa or a simpler tag-overlap ratio). This is something the project maintainer will compute from your spreadsheets — you don't need to calculate it yourself.
4. **Disagreements get adjudicated**, not averaged: annotators discuss the specific FOA together (or a third reviewer decides) to produce one final consensus label. The individual pre-adjudication answers are kept too, since that's what the agreement score is calculated from.
5. Non-overlapping FOAs can be split between annotators to cover more ground without duplicating effort.

---

## 7. Practical Notes

- **Time expectation:** budget roughly 5–15 minutes per FOA for a careful read and tagging pass across all five categories. For 50 FOAs with full overlap, that's 4–12 hours per annotator.
- **Annotator IDs, not names:** use an assigned code (e.g. `ANNOT_1`) in your spreadsheet so the dataset can be shared/reviewed without needing to track identity in the data file itself.
- **This is not human-subjects research** — you're labeling public funding-announcement text, not evaluating people — so no IRB review is expected to be needed, but check with your mentor/PI if your institution has a different policy.
- Questions about a specific FOA or category boundary should be written down as a confidence flag (§5) rather than resolved silently — those notes are valuable input for refining this codebook itself.
