"""
classical enhancement baselines
simple reference-free methods to compare against deep learning models.

"""

from __future__ import annotations
import logging
from pathlib import Path
import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


def _load_mono(path: Path, target_sr: int = 16000) -> tuple[np.ndarray, int]:
    """loads audio as mono array."""
    import librosa
    audio, sr = librosa.load(str(path), sr=target_sr, mono=True)
    return audio, sr


def run_noisereduce(input_path: Path, output_path: Path, target_sr: int = 16000) -> None:
    """runs simple spectral gating via noisereduce."""
    try:
        import noisereduce as nr
    except ImportError:
        raise ImportError("noisereduce not installed. run: pip install noisereduce")

    audio, sr = _load_mono(input_path, target_sr)
    logger.info("running noisereduce...")

    reduced = nr.reduce_noise(y=audio, sr=sr)
    sf.write(str(output_path), reduced, sr)
    logger.info(f"saved noisereduce output to {output_path.name}")


def run_wiener(input_path: Path, output_path: Path, target_sr: int = 16000) -> None:
    """runs standard wiener filter for comparison."""
    from scipy.signal import wiener
    audio, sr = _load_mono(input_path, target_sr)

    filtered = wiener(audio)
    sf.write(str(output_path), filtered.astype(np.float32), sr)
