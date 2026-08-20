"""
Layer 3: LLM Data Extraction

Uses local Ollama to extract structured JSON data from unstructured FOA text.
Specifically built to extract complex funding budget tiers from PDF text.
"""

import json
import logging
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)


class BudgetTierExtractor:
    """Extracts budget tiers from FOA text using Ollama."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral:7b-instruct",
    ):
        self.base_url = base_url
        self.model = model

        self.system_prompt = (
            "You are an expert grant data extractor. Extract funding budget tiers "
            "from the provided text.\n"
            "Output strictly valid JSON as an array of objects.\n"
            "Each object must have these keys exactly:\n"
            "- category: string (e.g. 'I', 'II', 'Seed', etc.)\n"
            "- min_award: number (minimum dollar amount, 0 if not specified)\n"
            "- max_award: number (maximum dollar amount, 0 if not specified)\n"
            "- duration_years: number (duration in years, 0 if not specified)\n\n"
            "If no budget tiers are mentioned, return an empty array [].\n"
            "Do NOT wrap the output in markdown code blocks, do not include "
            "explanations. Only return raw JSON."
        )

    def is_available(self) -> bool:
        """Check if Ollama server is running."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=2.0)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                if self.model in models or f"{self.model}:latest" in models:
                    return True
        except requests.RequestException:
            pass
        return False

    def extract_tiers(self, text: str) -> List[Dict[str, Any]]:
        """Extract budget tiers from text and return a list of dicts."""
        if not text or len(text.strip()) < 50:
            return []

        prompt = f"Extract budget tiers from this text:\n\n{text}"

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "system": self.system_prompt,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0},
                    "format": "json"
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            result_text = resp.json().get("response", "").strip()

            # Clean potential markdown wrapping
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]

            parsed = json.loads(result_text.strip())
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                if "tiers" in parsed:
                    return parsed["tiers"]
                if "data" in parsed:
                    return parsed["data"]
                # Fallback: return the first list value found
                for val in parsed.values():
                    if isinstance(val, list):
                        return val

        except Exception as exc:
            logger.warning("LLM Budget Extraction failed: %s", exc)

        return []
