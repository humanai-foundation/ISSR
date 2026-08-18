import os
import json
import logging
import librosa
import numpy as np
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class QCTagger:
    """
    Quality Control (QC) verification suite for Pyannote Diarization.
    Scans diarization output against raw audio features to flag anomalous segments.
    """
    
    def __init__(self, f0_min: float = 65.0, f0_max: float = 300.0, pitch_shift_threshold: float = 0.3):
        """
        Initialize the QC Tagger.
        
        Args:
            f0_min: Minimum expected human pitch (Hz)
            f0_max: Maximum expected human pitch (Hz)
            pitch_shift_threshold: Fractional shift (e.g. 0.3 = 30%) to flag as anomaly
        """
        self.f0_min = f0_min
        self.f0_max = f0_max
        self.pitch_shift_threshold = pitch_shift_threshold
        
    def _extract_pitch(self, audio_array: np.ndarray, sr: int) -> float:
        """Calculate median fundamental frequency (pitch) of an audio segment."""
        if np.max(np.abs(audio_array)) < 1e-4:
            return 0.0
            
        f0 = librosa.yin(audio_array, fmin=self.f0_min, fmax=self.f0_max, sr=sr)
        
        valid_f0 = f0[f0 > 0]
        if len(valid_f0) == 0:
            return 0.0
            
        return float(np.median(valid_f0))

    def process(self, diarization_segments: List[Dict[str, Any]], audio_path: str) -> List[Dict[str, Any]]:
        """
        Process the diarization segments against the raw audio to generate QC tags.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
        logger.info(f"Running QC Tagging on {len(diarization_segments)} segments...")
        
        y, sr = librosa.load(audio_path, sr=16000)
        
        speaker_pitches = {}
        segment_pitches = []
        
        for idx, seg in enumerate(diarization_segments):
            start_sample = int(seg['start'] * sr)
            end_sample = int(seg['end'] * sr)
            
            end_sample = min(end_sample, len(y))
            audio_chunk = y[start_sample:end_sample]
            
            pitch = self._extract_pitch(audio_chunk, sr)
            segment_pitches.append(pitch)
            
            speaker = seg['speaker']
            if speaker not in speaker_pitches:
                speaker_pitches[speaker] = []
                
            if pitch > 0:
                speaker_pitches[speaker].append(pitch)
                
        # Calculate baseline median pitch for each speaker
        speaker_baselines = {}
        for speaker, pitches in speaker_pitches.items():
            if len(pitches) > 0:
                speaker_baselines[speaker] = float(np.median(pitches))
            else:
                speaker_baselines[speaker] = 0.0
                
        qc_flags = []
        
        for idx, seg in enumerate(diarization_segments):
            speaker = seg['speaker']
            pitch = segment_pitches[idx]
            baseline = speaker_baselines[speaker]
            duration = seg['end'] - seg['start']
            
            flags = []
            
            if baseline > 0 and pitch > 0:
                shift = abs(pitch - baseline) / baseline
                if shift > self.pitch_shift_threshold:
                    flags.append(f"PITCH_SHIFT_{int(shift*100)}%")
                    
            if duration < 1.0:
                flags.append("MICRO_SEGMENT")
                
            if len(flags) >= 2:
                qc_flags.append({
                    "segment_id": idx,
                    "start": seg['start'],
                    "end": seg['end'],
                    "speaker": speaker,
                    "duration": round(duration, 2),
                    "segment_pitch": round(pitch, 1),
                    "speaker_baseline": round(baseline, 1),
                    "flags": flags
                })
                
        logger.info(f"QC Tagging complete. Found {len(qc_flags)} suspicious segments requiring manual review.")
        return qc_flags

    def save_report(self, qc_flags: List[Dict[str, Any]], output_path: str):
        """Save the flagged segments to a JSON report."""
        with open(output_path, 'w') as f:
            json.dump(qc_flags, f, indent=4)
        logger.info(f"Saved QC report to {output_path}")
