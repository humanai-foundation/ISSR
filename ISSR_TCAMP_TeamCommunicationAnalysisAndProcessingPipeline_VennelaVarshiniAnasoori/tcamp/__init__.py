"""
tcamp: team communication processing and analysis pipeline
developed for the trip lab to clean up driving simulator headset recordings.

author: vennela varshini anasoori
"""

__version__ = "0.1.0"

from .enhance import enhance_audio

__all__ = [
    "__version__",
    "enhance_audio",
]
