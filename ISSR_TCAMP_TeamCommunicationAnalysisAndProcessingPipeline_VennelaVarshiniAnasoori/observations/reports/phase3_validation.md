# Phase 3 Validation & Tuning (Transcription)

---

This document tracks the evaluation of the Segment-Level Dual-Path architecture and WhisperX transcription quality.

## Goal
To reduce transcription errors (Word Error Rate, missed speech, and hallucinations) by smartly selecting between RAW audio and DeepFilterNet-enhanced audio on a segment-by-segment basis.

## Implementation Strategy
1. **Diarization**: Extract speaker segments from RAW audio to guarantee no missed quiet speech.
2. **Selection Rule**: Compare RMS energy of the RAW segment vs the Enhanced segment. If the Enhanced segment's energy is suppressed by $>90\%$ (i.e. `< 10%` of RAW energy), use the RAW segment. Otherwise, use the Enhanced segment.
3. **Transcription**: Pass the selected segment to WhisperX.

## Evaluation Notes

### Prototype Run 1 (Local CPU)
- **Audio Sample**: `EN2002a.wav` (30-second chunk)
- **Model**: WhisperX (Tiny)
- **Results**: 


### Result Log from Prototype Run
```text
SPEAKER_00 [0.0 - 6.7] (Source: DFN): on the menu you can select a summarization box which pops up and an audio player.
SPEAKER_01 [8.2 - 8.5] (Source: DFN): Right
SPEAKER_00 [8.8 - 24.8] (Source: DFN): And I think the search works as well. So pop up a search. And it loads up just the background window so empty. And so when you start, you have to either open, open a particular observation or do a search and open it through that.
SPEAKER_00 [26.5 - 29.2] (Source: DFN): Does that make sense?
```

### Analysis
The results validate the Segment-Level Dual-Path approach.

1. **Lost Speech Recovered:** In Phase 1/Phase 2 testing, `SPEAKER_01` (who says "Right" at 8.2s) was missed from the output because DeepFilterNet altered the acoustic fingerprint, causing Pyannote's VAD to drop the segment. 
2. **Dual-Path Execution:** By running Diarization on the **RAW audio**, the pipeline correctly identified the `[8.2 - 8.5]` timestamps for `SPEAKER_01`. 
3. **Smart Segment Selection:** The pipeline extracted that exact segment and fed it to WhisperX. The Smart Selector logged `Source: DFN`, indicating DeepFilterNet didn't completely silence the audio (RMS was >10% of raw) but distorted it enough to affect Pyannote. WhisperX robustly transcribed "Right" from the DFN segment.

### Full Pipeline Integration
The prototype code was officially integrated into the core `tcamp/pipeline.py` script. The pipeline now executes three native steps:
1. Enhancement
2. Diarization (on RAW audio)
3. Transcription (Dual-Path Smart Selector)

### Colab Run (GPU)
- **Audio Sample**: Full AMI Meeting File (`EN2002a.wav`)
- **Model**: WhisperX (Large-v2)
- **Results**: 
  - **Execution**: The pipeline processed the full 50-minute meeting file on the T4 GPU.
  - **Overlapping Speech**: Handled overlapping segments accurately (e.g. `[106.2 - 134.8] SPEAKER_01` overlapping with `[106.2 - 106.7] SPEAKER_00`).
  - **Dual-Path Accuracy**: Pyannote detected micro-utterances ("Yeah", "Okay") and WhisperX transcribed them from the DFN enhanced audio.
  - **Hallucinations Addressed**: Implemented a 0.5s segment filter and regex-based artifact filter (e.g., `"you"`, `"[unintelligible]"`) in `pipeline.py` to strip known Whisper silence hallucinations.
