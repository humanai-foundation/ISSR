# TCAMP: Team Communication Processing and Analysis

GSoC 2026 Project | HumanAI Foundation | Institute for Social Science Research (ISSR) & TRIP Lab, University of Alabama
Contributor: Vennela Varshini Anasoori

---

## Overview
In simulator driving studies conducted by the Institute for Social Science Research (ISSR) and the TRIP Laboratory at the University of Alabama, teams talk through headsets. These recordings often catch low-frequency room hum, clicks, and echo. **TCAMP** cleans up this audio so speech is clearer for analysis, and then diarizes the audio to extract precise "who spoke when" timestamps.

The pipeline features 4 fully-integrated stages: Audio Enhancement, Speaker Diarization, Transcription, and Behavioral Analytics.

---

## Architecture: The Segment-Level Dual-Path Pipeline
The pipeline is divided into four core modules that execute sequentially, plus an advanced analytics engine to maximize both diarization accuracy and psychological insights.

### 1. Audio Enhancement (DeepFilterNet) & Video Support
Automatically extracts `.wav` tracks from `.mp4` video files using `ffmpeg`. Supports two options to remove background noise (standardized to 16000 Hz). The pipeline includes offline, reference-free evaluation (DNSMOS).
- `deepfilter`: Deep learning approach using DeepFilterNet3.
- `noisereduce`: Simple spectral gating fallback.

### 2. Speaker Diarization (Pyannote on RAW Audio)
Leverages `pyannote.audio` to segment the audio and cluster speaker identities. 
- **The Dual-Path Insight:** Diarization is executed on the **RAW audio** rather than the enhanced audio. Enhancement models like DeepFilterNet sometimes distort or suppress quiet speech, causing Pyannote's VAD to miss speakers. By using RAW audio, precise timestamps are extracted without losing quiet speech segments.
- Includes a built-in Diarization Error Rate (DER) evaluator that natively uses `pyannote.metrics`.

### 3. Smart Transcription (WhisperX)
Transcribes the audio segment-by-segment using WhisperX.
- **Smart Segment Selector:** For every timestamp found by Pyannote, the segment is extracted from *both* the RAW audio and the Enhanced audio. If the RMS energy of the enhanced segment is extremely low compared to the raw audio (indicating the enhancement model over-suppressed it), the RAW audio is passed to WhisperX. Otherwise, the clean Enhanced audio is used.
- **Model Selection (`medium.en`):** The pipeline is explicitly optimized for the `medium.en` model with strict `language="en"` constraints. This prevents multilingual hallucinations and avoids the "hallucinated fluency" (grammar autocorrecting) inherent to larger Whisper architectures.
- This results in highly accurate, verbatim text transcripts optimized for behavioral analytics.

### 4. Quality Control (Multi-Condition QC Tagger)
A post-diarization analytics module built to identify potential misattributions caused by acoustic anomalies.
- **Anomaly Detection:** Diarization models can struggle during sudden pitch shifts (e.g., mumbling, laughing). The `qc_tagger` uses `librosa.yin` to calculate the fundamental frequency (F0) baseline for each speaker.
- **Multi-Condition Flagging:** It mathematically flags any segment where the pitch deviates by >30% from the speaker's baseline AND the segment duration is < 1 second. This generates a targeted list of suspicious segments for manual review, reducing the need for LLM-based post-processing.

### 5. Behavioral Analytics Engine (Phase 4)
The final stage transforms acoustic and textual data into quantifiable human factors research.
- **Mathematical Signal Processing (`behavioral_metrics.py`):** Calculates 6 foundational metrics directly from the diarized timeline, including Silence Ratios (cognitive load), Interruption Rates (dominance), Response Latency, and the Gini Centralization Coefficient (team hierarchy).
- **Semantic NLP Tagging (`dialogue_tagger.py`):** Uses a local Llama 3.2 instance (via Ollama) running strictly in JSON Mode to perform zero-shot qualitative analysis. It extracts Psychological Safety Markers (e.g., Hedging), Sentiment Shifts (e.g., Frustration), and Dialogue Acts from every utterance, completely offline for clinical data privacy.
- **CSV Exporter (`export.py`):** Automatically flattens all JSON outputs into clean, statistical-analysis-ready `.csv` files for direct import into SPSS, R, or Excel.
- **Interactive Dashboard (`dashboard.py`):** A Plotly Dash web application for real-time visualization of KPIs, talk-time dominance, dialogue act breakdowns, sentiment timelines, and turn-taking Gantt charts.

---

## Setup
The environment is managed via Conda. You will also need a Hugging Face token (via `$env:HF_TOKEN`) to access Pyannote models.

```bash
# Create and activate environment
conda env create -f environment.yml
conda activate tcamp
```

---

## Usage
Use the CLI to run the full pipeline (Video Extraction -> Enhancement -> Diarization -> QC -> Transcription -> Phase 4 Analytics):

```bash
python run_pipeline.py -i observations/audio_samples/sample_meeting.mp4 --run-qc --run-analytics
```

*Note: You can override the transcription model if needed (e.g., `--transcription-model large-v2 --transcription-device cuda`).*

### Launch the Dashboard
```bash
python dashboard.py
# Open http://127.0.0.1:8050 in your browser
```

---

## Testing
To run the automated test suite across both enhancement and diarization modules:
```bash
python -m pytest tests/ -v -s
```

---

## Repository Structure

```text
├── tcamp/
│   ├── pipeline.py            # Core Segment-Level Dual-Path architecture router
│   ├── enhance/               # DeepFilterNet/NoiseReduce models and quality metrics
│   ├── diarization/           # Pyannote integration and DER tracking algorithms
│   ├── transcription/         # WhisperX integration
│   └── analytics/             # Behavioral metrics engine, Llama 3.2 tagger, and QC tagger
│
├── observations/
│   ├── audio_samples/         # Raw audio and video files (.wav, .mp4)
│   ├── ground_truths/         # Ground truth RTTM files for evaluation
│   ├── reports/               # Formal evaluation notes and ablation studies
│   └── outputs/               # Generated pipeline artifacts (JSONs, CSVs, Audio)
│
├── tests/                     # Pytest suite using real lab recordings
├── dashboard.py               # Plotly Dash interactive visualization dashboard
├── run_pipeline.py            # Unified CLI entry point for the pipeline
└── environment.yml            # Conda environment specifications
```

---

## Blog

Read the detailed technical writeup explaining the engineering pivots, dual-path architecture, and offline analytics here:
[Micro Rooms, Macro Noise: Engineering the TCAMP Architecture for Human-Factors Research](https://medium.com/@vennelavarshini07/micro-rooms-macro-noise-engineering-the-tcamp-architecture-for-human-factors-research-380235fc242b)

---

## Credits

Developed during **Google Summer of Code (GSoC) 2026** by **@vennelavarshini18**

**Organization:** HumanAI Foundation  
**Institute:** Institute for Social Science Research (ISSR), University of Alabama  
**Laboratory:** TRIP Lab, University of Alabama  
