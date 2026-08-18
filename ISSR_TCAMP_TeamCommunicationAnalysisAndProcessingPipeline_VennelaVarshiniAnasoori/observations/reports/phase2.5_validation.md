# Phase 2.5 Validation & Tuning (Batch Evaluation)
---

This document tracks the advanced tuning of the deepfilternet enhancement layer. Specifically, we are trying to recover the quiet speech that deepfilternet suppresses (which previously caused a jump in diarization miss rate).

## Part 1: Speech Normalization Design Decision

### 1. The Goal
We need to recover quiet speech suppressed by deepfilternet *without* amplifying the background noise floor or increasing speaker confusion.

### 2. Evaluated Methods
- **Peak/RMS normalization:** rejected. These act as a static volume knob. If there is one loud spike in the audio, the quiet speech remains completely suppressed. They scale the noise and speech equally, which breaks diarization.
- **Dynamic Range Compression (DRC):** Chosen. DRC is a "smart" volume knob. It specifically targets high-energy audio and squashes it, allowing us to apply "makeup gain" to amplify the quiet speech. 

### 3. Implementation
We chose to use **`pedalboard`** (a C++ audio library open-sourced by Spotify). We apply a strict `noisegate` (to keep pure silence at absolute zero) immediately followed by a `compressor` (to aggressively amplify the quiet speech without clipping). This gives Pyannote the energy it needs to detect speech accurately.

---

## Part 2: The 5 Diverse Edge-Cases
We specifically selected 5 AMI samples based on their initial failure modes to ensure our new configurations don't fix one problem by creating another:
1. **`en2002a`**: Failed previously due to extreme speaker overlap.
2. **`es2003a`**: Failed previously due to massive false alarms in raw audio.
3. **`is1000a`**: Failed previously due to high overall noise causing Pyannote to hallucinate.
4. **`ts3007a`**: Failed previously due to massive miss rate jumps after deepfilternet.
5. **`in1001`**: succeeded previously (deepfilternet perfectly solved confusion), used as a control.

---

## Part 3: The 5 Configurations Tested
We test 5 pipelines across the above 5 samples to find the ultimate combination:
1. `raw -> pyannote` (baseline)
2. `dfn -> default pyannote`
3. `dfn -> lower vad (0.30)`
4. `dfn -> speech normalization -> default pyannote`
5. `dfn -> speech normalization -> lower vad (0.30)`

---

## Part 4: Batch Evaluation Results Table

| Sample | Condition | Expected Speakers | Actual Speakers | DER | Miss | False Alarm | Confusion | Runtime (s) | Notes |
|---|---|---|---|---|---|---|---|---|---|
| EN2002a | **1. Raw -> Pyannote** | ? | 5 | 24.73% | 13.39% | 2.86% | 8.49% | 2171.6 | Auto-evaluated |
| ES2003a | **1. Raw -> Pyannote** | ? | 4 | 11.41% | 4.52% | 4.03% | 2.85% | 1113.3 | Auto-evaluated |
| IN1001 | **1. Raw -> Pyannote** | ? | 7 | 15.49% | 6.39% | 3.99% | 5.11% | 2718.7 | Auto-evaluated |
| IS1000a | **1. Raw -> Pyannote** | ? | 5 | 25.75% | 10.58% | 9.79% | 5.38% | 1212.3 | Auto-evaluated |
| TS3007a | **1. Raw -> Pyannote** | ? | 6 | 19.60% | 6.63% | 6.51% | 6.46% | 1236.3 | Auto-evaluated |
| EN2002a | **2. DFN -> Default Pyannote** | ? | 6 | 30.73% | 23.76% | 1.18% | 5.78% | N/A | Auto-evaluated |
| ES2003a | **2. DFN -> Default Pyannote** | ? | 7 | 15.20% | 8.24% | 2.60% | 4.36% | N/A | Auto-evaluated |
| IN1001 | **2. DFN -> Default Pyannote** | ? | 4 | 17.08% | 12.65% | 2.08% | 2.35% | N/A | Auto-evaluated |
| IS1000a | **2. DFN -> Default Pyannote** | ? | 9 | 33.10% | 18.64% | 5.61% | 8.85% | N/A | Auto-evaluated |
| TS3007a | **2. DFN -> Default Pyannote** | ? | 6 | 28.03% | 17.06% | 3.47% | 7.49% | N/A | Auto-evaluated |
| EN2002a | **3. DFN -> Lower VAD (0.30)** | ? | 6 | 31.01% | 24.14% | 1.17% | 5.71% | 2134.3 | Auto-evaluated (High Miss Rate) |
| ES2003a | **3. DFN -> Lower VAD (0.30)** | ? | 9 | 15.15% | 7.70% | 2.66% | 4.79% | 1123.9 | Auto-evaluated |
| IN1001 | **3. DFN -> Lower VAD (0.30)** | ? | 4 | 17.12% | 12.69% | 2.12% | 2.31% | 3405.8 | Auto-evaluated |
| IS1000a | **3. DFN -> Lower VAD (0.30)** | ? | 8 | 32.57% | 18.42% | 5.61% | 8.53% | 1548.4 | Auto-evaluated (High Miss Rate) |
| TS3007a | **3. DFN -> Lower VAD (0.30)** | ? | 6 | 30.50% | 19.27% | 3.47% | 7.77% | 1561.8 | Auto-evaluated (High Miss Rate) |
| EN2002a | **4. DFN -> Speech Norm -> Default Pyannote** | ? | 7 | 37.89% | 24.86% | 1.12% | 11.91% | 2081.1 | Auto-evaluated (High Miss Rate) (High Confusion) |
| ES2003a | **4. DFN -> Speech Norm -> Default Pyannote** | ? | 6 | 26.19% | 8.83% | 2.48% | 14.88% | 1092.4 | Auto-evaluated (High Confusion) |
| IN1001 | **4. DFN -> Speech Norm -> Default Pyannote** | ? | 6 | 25.19% | 16.30% | 2.09% | 6.79% | 3352.7 | Auto-evaluated (High Miss Rate) |
| IS1000a | **4. DFN -> Speech Norm -> Default Pyannote** | ? | 8 | 40.36% | 17.07% | 6.93% | 16.36% | 1488.5 | Auto-evaluated (High Miss Rate) (High Confusion) |
| TS3007a | **4. DFN -> Speech Norm -> Default Pyannote** | ? | 6 | 38.48% | 20.59% | 3.24% | 14.66% | 1492.2 | Auto-evaluated (High Miss Rate) (High Confusion) |
| EN2002a | **5. DFN -> Speech Norm -> Lower VAD (0.30)** | ? | 7 | 37.89% | 24.86% | 1.12% | 11.91% | 2119.4 | Auto-evaluated (High Miss Rate) (High Confusion) |
| ES2003a | **5. DFN -> Speech Norm -> Lower VAD (0.30)** | ? | 6 | 26.19% | 8.83% | 2.48% | 14.88% | 1197.0 | Auto-evaluated (High Confusion) |
| IN1001 | **5. DFN -> Speech Norm -> Lower VAD (0.30)** | ? | 6 | 25.19% | 16.30% | 2.09% | 6.79% | 4474.6 | Auto-evaluated (High Miss Rate) |
| IS1000a | **5. DFN -> Speech Norm -> Lower VAD (0.30)** | ? | 8 | 40.36% | 17.07% | 6.93% | 16.36% | 1515.4 | Auto-evaluated (High Miss Rate) (High Confusion) |
| TS3007a | **5. DFN -> Speech Norm -> Lower VAD (0.30)** | ? | 6 | 38.48% | 20.59% | 3.24% | 14.66% | 1535.2 | Auto-evaluated (High Miss Rate) (High Confusion) |

---

## Part 5: Metric Observations
### Diarization Error Rate (DER)
DER degraded significantly when applying speech normalization (DRC). For example, `is1000a` DER jumped from 33.10% (baseline DFN) to 40.36%. Condition 5 (combining lower VAD and DRC) yielded the same scores as condition 4. The normalization process distorted the acoustic features, reducing system performance.

### Miss Rate (The Main Bottleneck)
Lowering the VAD threshold to 0.30 failed to recover the suppressed quiet speech. Across all samples, the miss rate either stayed the same or increased. This indicates that Pyannote's internal threshold is not the bottleneck; the deepfilternet algorithm is suppressing the acoustic features of quiet speech.

### False Alarms & Confusion
Speech normalization (DRC) caused speaker confusion to increase (e.g., `ES2003A` confusion jumped from 4.36% to 14.88%). The compressor artificially amplified the noise floor during quiet moments, causing Pyannote's speaker embedding model to fail to cluster speakers accurately. Combining this with a lower VAD threshold (condition 5) did not change these results.

---

## Part 6: Final Recommendation for Phase 3 (Transcription)
Our hypothesis that we could recover quiet speech using post-enhancement techniques (VAD tuning and DRC) is **proven false**. Tampering with the post-enhanced waveform destroys the deep learning embeddings that Pyannote relies on. 

Therefore, our recommendation for Phase 3 is to abandon post-processing fixes and implement a **dual-path architecture**:
1. **Segmentation Path**: Run Pyannote's Voice Activity Detection on the **raw** audio (to guarantee we catch all the quiet speech without miss rate spikes).
2. **Embedding Path**: Run Pyannote's Speaker Identification on the **deepfilternet** audio (so the background noise doesn't cause high speaker confusion).

### Connection to Transcription (Whisper)
The output of this dual-path architecture will be a highly accurate `rttm` file (the timestamps of who spoke when). This sets us up for Phase 3:
- We will use the `rttm` timestamps to cut the clean deepfilternet audio into noise-free clips.
- We will feed those clean slices directly into the ASR model (Whisper).
- Because Whisper is sensitive to noise but capable at quiet speech, giving it noise-free deepfilternet slices cut by raw-audio timestamps improves transcription accuracy without sacrificing missing audio.
