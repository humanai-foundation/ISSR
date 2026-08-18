"""
Transcription module using WhisperX for Phase 3.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class TranscriptionPipeline:
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        """
        Initialize the WhisperX transcription pipeline.
        
        Args:
            model_size: Whisper model size (e.g., 'tiny', 'base', 'small', 'medium', 'large-v2').
            device: 'cpu' or 'cuda'.
            compute_type: Precision type ('int8' for CPU, 'float16' for GPU).
        """
        try:
            import torch
            # Fix for WhisperX 3.8.6 passing 'token' to Pyannote 3.1.1's Inference
            from pyannote.audio.core.inference import Inference
            _orig_inference_init = Inference.__init__
            def _safe_inference_init(self, *args, **kwargs):
                kwargs.pop('token', None)
                _orig_inference_init(self, *args, **kwargs)
            Inference.__init__ = _safe_inference_init
            
            import whisperx
        except ImportError:
            raise ImportError("whisperx is not installed. Run: pip install git+https://github.com/m-bain/whisperx.git")
            
        # Hardware override if CUDA is available
        if torch.cuda.is_available():
            logger.info("CUDA detected. Switching WhisperX to GPU.")
            device = "cuda"
            compute_type = "float16"
            
        logger.info(f"Loading WhisperX model '{model_size}' on {device} ({compute_type})...")
        self.device = device
        self.model = whisperx.load_model(model_size, device, compute_type=compute_type)

    def transcribe_audio(self, audio_input: Any, batch_size: int = 16, language: str = None) -> Dict[str, Any]:
        """
        Transcribes audio.
        
        Args:
            audio_input: Path to the .wav file OR a numpy array of shape (samples,) at 16000Hz.
            batch_size: Batch size for WhisperX processing.
            language: ISO language code (e.g., 'en'). If None, Whisper auto-detects.
            
        Returns:
            Dictionary containing the transcribed segments and text.
        """
        import whisperx
        import numpy as np
        
        if isinstance(audio_input, (str, Path)):
            if not os.path.exists(audio_input):
                raise FileNotFoundError(f"Audio file not found: {audio_input}")
            logger.info(f"Transcribing {audio_input}...")
            # WhisperX uses ffmpeg internally here
            audio = whisperx.load_audio(str(audio_input))
        else:
            # Assume it's a numpy array directly (bypasses ffmpeg)
            audio = np.asarray(audio_input, dtype=np.float32)
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)
        
        # Transcribe
        result = self.model.transcribe(audio, batch_size=batch_size, language=language)
        return result

    def align_transcript(self, result: Dict[str, Any], audio_path: str | Path) -> Dict[str, Any]:
        """
        Optionally align the transcript for precise word-level timestamps using Wav2Vec2.
        Note: This is computationally expensive and optional for the prototype.
        """
        import whisperx
        logger.info("Aligning transcript for precise timestamps...")
        model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=self.device)
        audio = whisperx.load_audio(str(audio_path))
        aligned_result = whisperx.align(result["segments"], model_a, metadata, audio, self.device, return_char_alignments=False)
        return aligned_result
