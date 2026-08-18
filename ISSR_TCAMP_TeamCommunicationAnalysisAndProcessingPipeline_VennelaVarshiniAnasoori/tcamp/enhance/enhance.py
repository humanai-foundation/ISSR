"""
audio enhancement core interface
removes background hum and simulator noise from headset recordings.

"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


class AudioEnhancer:
    def __init__(self):
        """Initializes the enhancement engine and caching state."""
        self._df_model = None
        self._df_state = None

    def enhance(
        self,
        input_path: str | Path,
        output_path: str | Path,
        method: Literal["deepfilter", "noisereduce"] = "deepfilter",
        target_sr: int = 16000,
        apply_normalization: bool = False,
    ) -> dict:
        """
        Cleans up audio using the chosen method.

        args:
            input_path: path to the raw .wav file
            output_path: path to save the cleaned .wav file
            method: 'deepfilter' or 'noisereduce'
            target_sr: sampling rate to enforce across the pipeline (default 16000)

        returns:
            dict with quality scores and method name
        """
        in_file = Path(input_path)
        out_file = Path(output_path)

        if not in_file.exists():
            raise FileNotFoundError(f"input file not found: {in_file}")

        out_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"running {method} on {in_file.name} (target {target_sr} hz)")

        if method == "deepfilter":
            self._run_deepfilter(in_file, out_file, target_sr, apply_normalization)
        elif method == "noisereduce":
            from .baseline import run_noisereduce
            run_noisereduce(in_file, out_file, target_sr)
        else:
            raise ValueError(f"unknown method '{method}'. choose 'deepfilter' or 'noisereduce'.")

        from .metrics import evaluate
        scores = evaluate(original_path=in_file, enhanced_path=out_file)
        scores["method"] = method

        logger.info(f"finished. scores: {scores}")
        return scores

    def _run_deepfilter(self, in_file: Path, out_file: Path, target_sr: int, apply_normalization: bool = False) -> None:
        """Runs DeepFilterNet3 enhancement and aligns output to target_sr."""
        try:
            from df.enhance import enhance, init_df
            from df.io import load_audio, save_audio
            # pyrefly: ignore [missing-import]
            import torchaudio.functional as F
        except ImportError:
            raise ImportError("deepfilternet or torchaudio not installed. check requirements.")

        if self._df_model is None or self._df_state is None:
            logger.info("loading deepfilternet model...")
            self._df_model, self._df_state, _ = init_df()
        else:
            logger.info("using cached deepfilternet model...")

        audio, _ = load_audio(str(in_file), sr=self._df_state.sr())
        
        # pyrefly: ignore [missing-import]
        import torch
        
        # chunk processing to prevent memory overflow
        chunk_size = 3 * 60 * self._df_state.sr()
        enhanced_chunks = []
        
        if audio.dim() == 1:
            audio = audio.unsqueeze(0)
            
        for i in range(0, audio.shape[1], chunk_size):
            chunk = audio[:, i:i+chunk_size]
            # enhance() natively preserves RNN state across sequential chunks
            enhanced_chunk = enhance(self._df_model, self._df_state, chunk)
            enhanced_chunks.append(enhanced_chunk)
            
        enhanced = torch.cat(enhanced_chunks, dim=1)

        # standardize back to target frequency before saving
        if self._df_state.sr() != target_sr:
            logger.info(f"resampling deepfilter output from {self._df_state.sr()} to {target_sr} hz")
            enhanced = F.resample(enhanced, self._df_state.sr(), target_sr)

        if apply_normalization:
            enhanced = self._apply_dynamic_range_compression(enhanced, target_sr)

        save_audio(str(out_file), enhanced, target_sr)
        logger.info(f"saved deepfilter output to {out_file.name} at {target_sr} hz")

    def _apply_dynamic_range_compression(self, audio_tensor, sample_rate: int):
        """Applies pedalboard dynamic range compression to recover suppressed speech."""
        logger.info("applying dynamic range compression (DRC)...")
        try:
            from pedalboard import Pedalboard, Compressor, NoiseGate, Gain
            import torch
        except ImportError:
            raise ImportError("pedalboard is not installed. Run: pip install pedalboard")
            
        # Audio from df is a torch tensor [1, samples] in range [-1, 1]
        audio_np = audio_tensor.numpy()
        
        # apply dynamic range compression (noisegate -> compressor -> gain) to recover quiet speech
        board = Pedalboard([
            NoiseGate(threshold_db=-60.0, ratio=10, attack_ms=1.0, release_ms=100.0),
            Compressor(threshold_db=-30.0, ratio=4.0, attack_ms=5.0, release_ms=100.0),
            Gain(gain_db=15.0)
        ])
        
        processed_np = board(audio_np, sample_rate)
        return torch.from_numpy(processed_np)

# Keep the old function for backwards compatibility with test scripts
_default_enhancer = None

def enhance_audio(
    input_path: str | Path,
    output_path: str | Path,
    method: Literal["deepfilter", "noisereduce"] = "deepfilter",
    target_sr: int = 16000,
    apply_normalization: bool = False,
) -> dict:
    global _default_enhancer
    if _default_enhancer is None:
        _default_enhancer = AudioEnhancer()
    return _default_enhancer.enhance(input_path, output_path, method, target_sr, apply_normalization)
