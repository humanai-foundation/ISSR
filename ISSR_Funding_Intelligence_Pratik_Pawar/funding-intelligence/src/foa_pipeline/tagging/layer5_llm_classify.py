"""
Layer 5: LLM Classification Backstop.

L1 (exact match) and L2 (embedding similarity) leave some FOAs with zero tags
across every category -- not because they lack real content, but because
their best L2 score falls just under a precision-tuned threshold, or because
their subject matter (e.g. defense-technical programmes) sits outside what
the current 84-concept ontology was built to describe. Confirmed by direct
inspection: 204/1705 FOAs in the broadened (all-agency) corpus get nothing
from L1+L2+L3+CFDA, and many of them have 500+ characters of substantive,
clearly on-topic text -- L2's own unthresholded scores for these are real
and close (e.g. 0.346 against a 0.35 threshold), just not close enough.

This layer only ever runs on an FOA that already produced zero evidence from
every other layer -- it is a recall backstop, not a replacement for the
cheaper, faster, more precise cascade ahead of it. Opt-in via `tag-all
--llm-backstop`: unlike L3 (which answers a narrow A-or-B question for a
handful of close calls), this asks an open-ended "what applies here"
question against the whole ontology for every FOA it touches, which is a
meaningfully slower and more failure-prone task. Keeping it off by default
preserves the fast tag-all/evaluate iteration loop the rest of this project's
tuning history depends on.

One prompt per ontology category (not one big prompt listing all 84
concepts) -- the same design synthetic_annotator.py already validated for
silver-set generation: a 7B model handles an 8-25 option list far more
reliably than one long one. Written fresh here rather than imported from
synthetic_annotator.py to keep production tagging and evaluation-set
generation independently changeable; the prompt text is deliberately close
to that proven design.
"""

import json
import logging
from typing import Dict, List

import requests

from ..ontology.store import OntologyConcept, OntologyStore
from .evidence import TagEvidence

logger = logging.getLogger(__name__)

# Concepts contributed per category by this layer. A cheap defensive bound,
# independent of the full-list-echo guard below: even a validated response
# should not let one open-ended prompt dump an unbounded number of tags onto
# a single FOA.
MAX_CONCEPTS_PER_CATEGORY = 5

CATEGORY_PROMPTS = {
    "sponsor_theme": (
        "You are a US federal grants analyst. Read this grant program description and identify "
        "which GREAT Act mission categories apply. A category applies ONLY if the grant explicitly "
        "funds research or activities in that area.\n\n"
        "Available Categories:\n{concepts}\n\n"
        "Grant Description:\n{text}\n\n"
        "Return a JSON list of the matching concept IDs. If none match, return []. "
        "Example: [\"great_01\", \"great_05\"]\n"
        "JSON:"
    ),
    "research_domain": (
        "You are a UN Sustainable Development Goals expert. Read this grant program description "
        "and identify which UN SDGs are directly addressed. An SDG applies ONLY if the grant "
        "explicitly funds work related to that goal.\n\n"
        "Available SDGs:\n{concepts}\n\n"
        "Grant Description:\n{text}\n\n"
        "Return a JSON list of the matching concept IDs. If none match, return []. "
        "Example: [\"sdg_04\", \"sdg_13\"]\n"
        "JSON:"
    ),
    "method": (
        "You are a research methodology expert. Read this grant program description and identify "
        "which research methods are explicitly required or encouraged. A method applies ONLY if "
        "the grant specifically mentions or requires that research approach.\n\n"
        "Available Methods:\n{concepts}\n\n"
        "Grant Description:\n{text}\n\n"
        "Return a JSON list of the matching concept IDs. If none match, return []. "
        "Example: [\"method_01\", \"method_15\"]\n"
        "JSON:"
    ),
    "population": (
        "You are a demographics and equity expert. Read this grant program "
        "description and identify which target populations are explicitly "
        "mentioned as focus groups, beneficiaries, or required "
        "study subjects. A population applies ONLY if the grant explicitly targets that group.\n\n"
        "Available Populations:\n{concepts}\n\n"
        "Grant Description:\n{text}\n\n"
        "Return a JSON list of the matching concept IDs. If none match, return []. "
        "Example: [\"pop_03\", \"pop_12\"]\n"
        "JSON:"
    ),
    "research_discipline": (
        "You are an NSF programme officer. Read this grant program description and decide "
        "which NSF directorate would fund this research.\n\n"
        "Available Directorates:\n{concepts}\n\n"
        "Grant Description:\n{text}\n\n"
        "Rules:\n"
        "- Choose based on the SUBJECT of the research, not on words that merely appear.\n"
        "- Most grants belong to exactly ONE directorate. Return two only for genuinely "
        "interdisciplinary programmes, and never more than two.\n"
        "- Choose STEM Education only when the research studies teaching or learning itself, "
        "not when a grant merely trains students or has education outreach.\n"
        "- Choose Technology Innovation and Partnerships only for commercialisation, "
        "technology transfer or industry partnership programmes.\n"
        "- If the description is too generic to tell, return [].\n\n"
        "Return a JSON list of the matching concept IDs. Example: [\"nsf_bio\"]\n"
        "JSON:"
    ),
}


class LLMClassifier:
    """LLM classification backstop using Ollama, gated to zero-evidence FOAs."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral:7b-instruct",
    ):
        self.base_url = base_url
        self.model = model

    def is_available(self) -> bool:
        """Check if Ollama server is running and model is available."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=2.0)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                if self.model in models or f"{self.model}:latest" in models:
                    return True
                logger.warning("Ollama is running, but model '%s' not found.", self.model)
        except requests.RequestException:
            logger.warning("Ollama server not reachable at %s", self.base_url)
        return False

    def _call_ollama(self, prompt: str, max_retries: int = 2) -> List[str]:
        """Call Ollama in JSON mode, return the raw list of candidate concept IDs."""
        for attempt in range(max_retries + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.0, "num_predict": 256},
                    },
                    timeout=120.0,
                )
                resp.raise_for_status()
                result_text = resp.json().get("response", "").strip()
                parsed = json.loads(result_text)

                # Two response shapes observed from the model in practice:
                #   ["great_01", "great_05"]                  -> a plain list
                #   {"great_05": ["chemical synthesis", ...]}  -> concept ID as the key
                # Collect from both; the caller validates against real concept
                # IDs, so over-collecting here is harmless.
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
                if isinstance(parsed, dict):
                    candidates = list(parsed.keys())
                    for v in parsed.values():
                        if isinstance(v, list):
                            candidates.extend(str(x) for x in v)
                    return candidates
                return []

            except json.JSONDecodeError:
                if attempt < max_retries:
                    continue
                return []
            except Exception as exc:
                if attempt < max_retries:
                    continue
                logger.error(
                    "LLM classification call failed after %d attempts: %s",
                    max_retries + 1, exc,
                )
                return []
        return []

    def classify(self, full_text: str, store: OntologyStore) -> List[TagEvidence]:
        """
        Classify `full_text` against every ontology category.

        Only meaningful to call on an FOA that already has zero evidence from
        every other layer -- see the module docstring for why.
        """
        if not full_text.strip():
            return []

        text_truncated = full_text[:4000]
        results: List[TagEvidence] = []

        for category, prompt_template in CATEGORY_PROMPTS.items():
            concepts = store.get_concepts_by_category(category)
            if not concepts:
                continue

            concept_list = "\n".join(f"- {c.concept_id}: {c.label}" for c in concepts)
            prompt = prompt_template.format(concepts=concept_list, text=text_truncated)

            candidates = self._call_ollama(prompt)
            valid_by_id: Dict[str, OntologyConcept] = {c.concept_id: c for c in concepts}
            validated = [cid for cid in dict.fromkeys(candidates) if cid in valid_by_id]

            # Same guard synthetic_annotator.py uses: a response that echoes
            # back most/all of a category's concept list is a failure mode
            # (the model dumping the option list, not making a judgement),
            # not a genuine multi-label answer -- discard it rather than let
            # it pollute production tags.
            if len(valid_by_id) >= 4 and len(validated) > 0.5 * len(valid_by_id):
                logger.warning(
                    "LLM classification discarded for %s: %d/%d concepts "
                    "returned (looks like a full-list echo)",
                    category, len(validated), len(valid_by_id),
                )
                continue

            for concept_id in validated[:MAX_CONCEPTS_PER_CATEGORY]:
                concept = valid_by_id[concept_id]
                results.append(
                    TagEvidence(
                        concept_id=concept.concept_id,
                        label=concept.label,
                        category=concept.category,
                        source_layer="layer_5_llm_classify",
                        # Below L1 (1.0) and L3 (0.95): an open-ended "what
                        # applies here" judgement over the full ontology,
                        # with no embedding-similarity grounding behind it.
                        confidence=0.75,
                        context_snippet=text_truncated[:500],
                        ontology_concept_id=concept.concept_id,
                    )
                )

        return results
