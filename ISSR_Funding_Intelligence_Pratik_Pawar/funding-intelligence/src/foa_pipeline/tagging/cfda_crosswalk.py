"""
CFDA Crosswalk (Recall Backstop)

Maps CFDA (Assistance Listing) prefixes to Mission Categories.
Used as a fallback if the semantic taggers fail to identify a Mission Category.
"""

import re
from typing import Dict, Optional

# Map CFDA prefixes to Great Act concept_ids
CFDA_TO_GREAT_ACT: Dict[str, str] = {
    "10": "great_07",  # USDA -> Agriculture
    "12": "great_01",  # DoD -> National Defense
    "15": "great_06",  # DOI -> Natural Resources and Environment
    "16": "great_14",  # DOJ -> Administration of Justice
    "19": "great_10",  # State -> International Affairs
    "20": "great_08",  # DOT -> Transportation
    "47": "great_05",  # NSF -> General Science
    "66": "great_06",  # EPA -> Natural Resources and Environment
    "81": "great_04",  # DOE -> Energy
    "84": "great_09",  # ED -> Education and Training
    "93": "great_02",  # HHS/NIH -> Health
}

def apply_cfda_crosswalk(text: str) -> Optional[str]:
    """
    Look for a CFDA number (XX.YYY) in the text and return the corresponding
    Great Act concept_id if found.
    """
    # Look for CFDA or Assistance Listing Number pattern: e.g., 47.074
    match = re.search(r'\b(\d{2})\.\d{3}\b', text)
    if match:
        prefix = match.group(1)
        return CFDA_TO_GREAT_ACT.get(prefix)
    return None
