"""
Layer 3: LLM Disambiguation

Uses local Ollama (Mistral-7b) to resolve ambiguous tag assignments from Layer 2.
Triggers when two concepts in the same category have very close similarity scores.
"""

import json
import logging
from pathlib import Path
from typing import Optional

import requests

from .evidence import TagEvidence

logger = logging.getLogger(__name__)


class L3Tagger:
    """LLM tag disambiguation using Ollama."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral:7b-instruct",
        prompt_template_path: Optional[Path] = None,
    ):
        self.base_url = base_url
        self.model = model

        self.prompt_template = ""
        if prompt_template_path and prompt_template_path.exists():
            with open(prompt_template_path, encoding="utf-8") as f:
                self.prompt_template = f.read()
        else:
            # Fallback template
            self.prompt_template = (
                "Given this FOA excerpt:\n{foa_text}\n\n"
                "Which category fits best?\n"
                "A: {candidate_a} (sim: {score_a:.2f})\n"
                "B: {candidate_b} (sim: {score_b:.2f})\n"
                "Respond with A or B and a short reason."
            )

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

    def disambiguate(
        self,
        evidence_a: TagEvidence,
        evidence_b: TagEvidence,
        foa_text: str,
    ) -> TagEvidence:
        """
        Ask LLM to choose between two conflicting tags.
        Returns the winning TagEvidence with updated layer and confidence.
        """
        # Prepare context - prefer the snippet from the higher confidence tag
        context = evidence_a.context_snippet
        if not context and evidence_b.context_snippet:
            context = evidence_b.context_snippet

        if not context:
            context = foa_text[:1000]

        prompt = self.prompt_template.format(
            foa_text=context,
            candidate_a=evidence_a.label,
            score_a=evidence_a.confidence,
            candidate_b=evidence_b.label,
            score_b=evidence_b.confidence,
        )

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1},
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            result_text = resp.json().get("response", "").strip()

            winner_letter = None
            try:
                parsed = json.loads(result_text)
                if isinstance(parsed, dict):
                    winner_letter = str(parsed.get("winner", "")).strip().upper()
            except json.JSONDecodeError:
                logger.debug(
                    "L3 response was not valid JSON, falling back to substring parsing: %r",
                    result_text,
                )

            if winner_letter not in ("A", "B"):
                # Fallback: substring heuristic, for models/responses that
                # don't respect JSON mode.
                if result_text.startswith("A") or "candidate a" in result_text.lower():
                    winner_letter = "A"
                elif result_text.startswith("B") or "candidate b" in result_text.lower():
                    winner_letter = "B"

            if winner_letter == "A":
                winner = evidence_a
                loser = evidence_b
            elif winner_letter == "B":
                winner = evidence_b
                loser = evidence_a
            else:
                # Fallback to score if parsing failed entirely
                winner = (
                    evidence_a
                    if evidence_a.confidence >= evidence_b.confidence
                    else evidence_b
                )
                loser = evidence_b if winner == evidence_a else evidence_a

            # Return a new evidence object representing the L3 decision
            return TagEvidence(
                concept_id=winner.concept_id,
                label=winner.label,
                category=winner.category,
                source_layer="layer_3_llm",
                confidence=0.95,  # High confidence because LLM resolved it
                context_snippet=f"[Resolved against {loser.label}] {winner.context_snippet}",
                ontology_concept_id=winner.concept_id,
            )

        except Exception as exc:
            logger.error("LLM disambiguation failed: %s", exc)
            # Fallback to the one with the higher L2 score
            return evidence_a if evidence_a.confidence >= evidence_b.confidence else evidence_b
