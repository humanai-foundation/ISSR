"""
Automated Evidence Logging — provenance metadata for every tag.

Every assigned tag carries:
- source_layer: Which tagging layer produced it
- confidence_score: 1.0 for Layer 1, cosine for Layer 2
- context_snippet: The exact text that triggered the match
"""

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class TagEvidence:
    """Provenance metadata for a single tag assignment."""

    concept_id: str
    label: str
    category: str       # research_domain | method | population | sponsor_theme
    source_layer: str   # layer_1_terminological | layer_2_embedding | layer_3_llm
    confidence: float   # 1.0 for exact match, cosine similarity for embedding
    context_snippet: str  # The text that triggered this tag
    ontology_concept_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_tag_record(self) -> dict:
        """Convert to the tag format used in the FOA JSON schema."""
        return {
            "tag_id": f"{self.source_layer}:{self.concept_id}",
            "label": self.label,
            "category": self.category,
            "source_layer": self.source_layer,
            "confidence": round(self.confidence, 4),
            "context_snippet": self.context_snippet[:500],
            "ontology_concept_id": self.concept_id,
        }

    def __repr__(self) -> str:
        return (
            f"TagEvidence({self.label!r}, layer={self.source_layer}, "
            f"conf={self.confidence:.3f})"
        )
