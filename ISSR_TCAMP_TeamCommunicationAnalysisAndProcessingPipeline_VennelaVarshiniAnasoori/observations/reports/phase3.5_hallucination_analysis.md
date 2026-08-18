# Phase 3.5: Hallucination Investigation & Model Selection

---

This document tracks the investigation of WhisperX failure modes. The pipeline occasionally hallucinated foreign languages (Korean, Swedish) and phonetic nonsense ("Mermaid") during English-only meetings. The goal was to identify the root cause instead of using an LLM post-processing filter.

## Part 1: Goal & Setup

**Goal:** Isolate the cause of the hallucinations to determine if they are a pipeline flaw or predictable model behavior.

**Setup:** The exact timestamps of hallucinations in the `EN2002a` sample were isolated. These audio chunks were tested using an isolated script with four Whisper models: `base.en`, `medium.en`, `large-v2`, and `large-v3-turbo`. The `language="en"` parameter was strictly enforced to control the multilingual latent space. The raw audio was then manually inspected at those timestamps to find the acoustic ground truth.

---

## Part 2: Observations

### 1. Multilingual Hallucinations
Previously, Whisper hallucinated Korean and Swedish during silent or noisy segments. 
- **Observation:** When the `language="en"` parameter was enforced, 100% of the foreign language hallucinations disappeared across all four models.
- **Conclusion:** The issue was caused by Whisper's auto-language detection failing on ambient noise. Locking the language to English forced the models to output valid English sentences (e.g., turning the Korean hallucination into "We'll just say no for now").

### 2. Phonetic Hallucinations (The "Mermaid" Problem)
Previously, Whisper output phonetic nonsense like "Mermaid" at timestamp `1342.9`.
- **Observation:** Manual inspection of the audio showed that the timestamp contained a cough or chair squeak that bypassed the VAD filter. 
- **Conclusion:** Since the models were locked to English, they stopped guessing foreign words. Instead, Whisper tried to map the non-speech noise to the closest English phonetic equivalent, guessing "money" or "my name" instead of "Mermaid".

### 3. Overlapping Speech
- **Observation:** During overlapping speech, Whisper consistently dropped the secondary speaker.
- **Conclusion:** Whisper is a single-stream decoder, so overlapping text is lost. However, Pyannote accurately captures the timestamps of both speakers. This allows for interruption metrics to be calculated mathematically in Phase 4 without needing the text.

---

## Part 3: Model Comparison & Selection

The four architectures were compared to select a default model for the pipeline:

- **`base.en`:** Faithful to the raw audio (transcribes exactly what it hears, including stutters). However, it struggles with background noise due to its smaller size.
- **`large-v2` / `large-v3-turbo`:** Highly accurate but suffer from over-correction. These models act like an autocorrect, rewriting broken human grammar and deleting stutters to make perfect sentences. This removes verbatim accuracy needed for behavioral analytics.
- **`medium.en`:** Provides a balance. It has a robust acoustic model to filter ambient noise better than `base.en`, but it does not aggressively auto-correct grammar like the large models.

### Final Selection
**`medium.en`** is selected as the default transcription architecture. It provides acoustic robustness for noisy meeting rooms while preserving the exact phrasing needed for behavioral analysis.

---

## Part 4: Conclusion
Phase 3 (Transcription Validation) is closed. The pipeline is stable, and the remaining transcription anomalies are identified as standard limitations of current audio models, not pipeline bugs. 
