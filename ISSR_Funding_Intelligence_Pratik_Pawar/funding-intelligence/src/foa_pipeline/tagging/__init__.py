"""Three-layer semantic tagging engine (terminological, embedding, LLM)."""

from .evidence import TagEvidence
from .layer1_spacy import L1Tagger
from .layer2_embedding import L2Tagger
from .layer3_llm import L3Tagger
from .pipeline import TaggerPipeline

__all__ = ["TaggerPipeline", "L1Tagger", "L2Tagger", "L3Tagger", "TagEvidence"]
