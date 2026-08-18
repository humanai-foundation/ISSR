# Progress Log

## Phase 1: Basic Module Setup (weeks 1-2)
Goal: set up the repository structure and test out early audio enhancement models.

### May 9: Initial Meeting
- Met with mentors to discuss goals and workflow
- Agreed to keep code simple and easy to test with different models later
- Updates will be shared regularly through mails and weekly/biweekly meetings

### May 11: Module Layout
- Moved screening notebooks into `screening_notebooks/` to keep them safe
- Built basic enhancement tools in `tcamp/enhance/`:
  - `enhance.py`: routes audio to the selected model
  - `baseline.py`: runs simple options like noisereduce
  - `metrics.py`: calculates audio scores (stoi, si-sdr)

### May 14: Testing and Updates
- Added complete requirements list including deepfilternet and compatible torch versions
- Added pytest suite to test code using real headset samples
- Noticed that deepfilternet automatically converts audio to 48kHz, which causes unaligned evaluation scores when directly compared to 16kHz references. will discuss alignment options with mentors next week.

### May 26: Second Meeting
- Had second meeting with mentors Josh and Piyush.
- Discussed the sampling rate mismatch issue (16khz input vs 48khz deepfilter output).
- Mentors advised standardizing the sampling rate across the entire pipeline.
- Confirmed with mentors that everything must run locally (no cloud apis).

### May 31: Pipeline Standardization
- Implemented `target_sr` in the enhancement router. deepfilternet outputs are now automatically resampled back to 16000 hz before saving and evaluation.
- Metric alignment is fully fixed, deepfilter stoi score jumped to 0.9988 on the aligned scale.

### June 1: Local DNSMOS Integration
- Successfully integrated the `speechmos` library for completely offline, local DNSMOS evaluation.
- Updated the test suite to calculate and record DNSMOS scores alongside STOI and SI-SDR.
- The pipeline is now fully compliant with our strict local execution req (zero cloud APIs).

### June 2: Third Meeting
- Showed the pipeline to mentors, but deepfilter didn't run.
- Found out it was because python 3.14 doesn't support the required PyTorch wheels yet.
- Mentors told to fix the environment first and switch to a Conda environment with Python 3.12.

### June 4: Fixing the Environment (Phase 1 Complete)
- Moved the project to a new conda environment using python 3.12
- Locked exact versions for torch, torchaudio, and speechmos in `requirements.txt` so everyone has the exact same setup
- Tested the pipeline locally and deepfilternet gave good scores (stoi: 0.9988, si-sdr: 36.638 db, dnsmos: 3.0126)
- Finished phase 1

### June 6: Phase 2 Diarization & Pipeline Setup
- Started phase 2 by adding `pyannote.audio` to identify speakers
- The code now tracks who spoke when from the cleaned audio
- Added code to calculate diarization error rate (der) to measure accuracy
- Cleaned up the repository
- Built a single script (`run_pipeline.py`) that runs enhancement, diarization, and evaluation together
- Fixed a bug in `speechbrain` that was crashing the tests on windows
- Added a feature to automatically find and evaluate against the ground-truth rttm file

### June 13: Phase 2 Evaluation & Edge Cases
- Made an `environment.yml` to standardize the local setup
- Added `.rttm` file generation and a `--num-speakers` argument
- Updated der calculation to include miss, false alarm, and confusion rates
- Added `evaluate_batch.py` to test multiple files automatically

### June 16: Fourth Meeting
- Discussed about the batch evaluation result on ami sample about deepfilter affecting miss rate metric
- Concluded to run a mass batch evaluation on diverse multiple ami samples 

### June 20: Mass Batch Evaluation 
- Evaluated 10 standard ami corpus datasets
- Ran the evaluation script across all files for raw, noisereduce, and deepfilternet
- Added audio chunking in `enhance.py` to fix memory crashes on large audio files
- Noticed that `noisereduce` messes up diarization by erasing voice features, which causes the confusion rate to go up
- Noticed that `deepfilternet` preserves speaker identity better, but it's a bit too aggressive and suppresses quiet speech, causing the miss rate to go up

### June 21: Tuning for next phase
- Moved deepfilternet initialization into an `AudioEnhancer` class in `enhance.py` so the model doesn't reload constantly during batch runs
- Lowered pyannote's segmentation threshold to 0.30 to make it more sensitive to the quiet speech that deepfilternet suppresses

### June 23: Fifth Meeting
- Discussed midterm expectations.
- Decided deepfilternet stays as the primary enhancement model, identified miss rate as the main bottleneck
- Agreed to run a 4-step validation experiment across diverse ami samples to find a way to recover quiet speech without increasing false alarms or confusion.
- Discussed exploring a post-filter speech normalization method 

### June 25: Phase 2.5 Tuning & Batch Setup
- Selected dynamic range compression (drc) using the `pedalboard` package to recover suppressed speech without amplifying background noise
- Implemented `_apply_dynamic_range_compression` in the enhancement module using a noisegate and compressor
- Modified the batch evaluation script to test 5 specific edge-case ami samples across 5 different pipeline configurations

### June 27: Phase 2.5 Results & Phase 3 Architecture
- Completed the 5-step batch validation experiments on the edge-case ami files
- Concluded that post-processing cannot recover the quiet speech without breaking diarization
- Documented all findings 

### June 28: GPU Migration & Code Cleanup
- Recognized that running Pyannote on CPU is a massive bottleneck (taking >30 mins per file)
- Migrated the repository execution to google colab (t4 gpu) using a github + google drive hybrid approach

### June 30: Sixth Meeting
- Discussed the phase 2.5 results with mentors.
- Piyush suggested a completely different architectural approach: "Segment-Level Dual Path".
- Instead of trying to fix DeepFilterNet to work with Pyannote, we will use RAW audio for Diarization (to find perfect timestamps) and use DeepFilterNet audio for Transcription (to get perfect text).

### July 2: Phase 3 Setup 
- Prototyped `prototype_dual_path.py` to test the Dual-Path theory.
- Introduced `whisperx` for transcription.

### July 5: Phase 3 Colab Run & Completion
- Built the Segment-Level Dual-Path architecture directly into `pipeline.py`
- Fed raw audio to diarization and enhanced audio to whisperx
- Ran the prototype on colab gpu on a 50-minute meeting and confirmed it perfectly recovered previously lost speech
- Added a quick filter to remove annoying whisper hallucinations

### July 8: Seventh Meeting
- Finalized the segment-level dual-path architecture as the direction for transcription
- Identified minor whisper hallucinations as remaining transcription issue
- Discussed the upcoming shift to the text analytics phase for the second half of gsoc

### July 9: Midterm Submission
- Submitted the gsoc midterm contributor evaluation form 

### July 10: Midterm Pass & Feedback
- Passed the gsoc midterm evaluation
- Mentors advised to continue documenting metrics and methods throughout the development cycle

### July 11: Whisper Hallucination Analysis
- Analyzed whisper hallucinations in the AMI dataset.
- Identified that the current dual-path pipeline and zero-speech vad filters inherently solve the whisper hallucination problem without needing a post-processing layer.
- Documented findings in `observations/hallucination_analysis.md`.

### July 14: Eighth Meeting
- Mentors confirmed the current dual-path pipeline is reproducible.
- Decided to pause phase 4 to investigate why whisper occasionally hallucinates.

### July 18: Phase 3.5 Hallucination Analysis
- Completed MANUAL ground-truth inspection of EN2002a hallucinations.
- Generated base.en, medium.en, large-v2, and large-v3-turbo transcriptions and compared the models side-by-side.
- Officially selected `medium.en` as the default model due to its balance of acoustic robustness and verbatim faithfulness.
- Prepared `phase3.5_hallucination_analysis.md` and diagrams

### July 21: Ninth Meeting
- Discussed the phase 3.5 hallucination analysis findings.
- Proposed and received approval for a "Multi-Condition QC Tagger" to mathematically flag diarization errors based on sudden pitch shifts and short segment durations.

### July 24: Phase 3.5 QC Tagger Completion
- Designed and implemented the Multi-Condition QC Tagger using `librosa.yin` for fundamental frequency (F0) tracking.
- Ran the updated pipeline on `EN2002a`. The QC tagger successfully filtered 976 diarized segments down to 249 suspicious segments that matched the exact acoustic profile of Pyannote misattributions (pitch shift + micro-segment).

### July 25: Phase 3.5 Final Validation & Documentation
- Ran the full pipeline (with `--run-qc`) on an additional diverse AMI sample (`IS1009a`, Idiap corpus with non-native accents).
- Successfully validated that the `medium.en` model handles heavily accented speech without foreign language hallucinations.
- Validated the Multi-Condition QC Tagger across different acoustic profiles; it successfully isolated 32 anomalous segments for manual review.

### July 30: Tenth Meeting
- Confirmed the pipeline's stability and readiness for Phase 4 (Behavioral Analytics).
- Decided to build a foundational Metrics Extraction Block (Talk Time, Silence Ratio, Interruptions) before integrating LLM text tagging.
- Mentors agreed to provide a TRIP Lab audio sample (6 speakers) to formally stress-test the pipeline.

### August 1: Codebase Audit
- Updated `environment.yml` to include all recent dependencies (`librosa`, `soundfile`).
- Cross-referenced the current pipeline against deliverables defined in the GSoC Proposal to ensure complete Phase 1-3 coverage.

### August 2: Phase 4 POC Implementation
- Defined the specific NLP goals for Phase 4 in `phase4_roadmap.md`.
- Built the core Analytics Engine to mathematically extract 6 GSoC metrics (Talk Time, Silence Ratio, Turn-Taking, Interruptions, Response Latency, Gini Centralization).
- Built the local AI tagging hook to pass pipeline transcripts to a local Llama 3.2 instance (via Ollama) for zero-shot Dialogue Act classification.
- Ran `test_analytics.py` on the AMI corpus (`EN2002a` and `IS1009a`); proved the pipeline can extract behavioral signals and semantic intents completely locally.

### August 6: MP4 Video Support & NLP Expansion
- Reorganized the `observations/` folder into logical subdirectories for easy navigation.
- Modified `tcamp/pipeline.py` to automatically detect `.mp4` video files and extract the audio track to `.wav` using `ffmpeg` before processing.
- Expanded the `dialogue_tagger.py` prompt to force Llama 3.2 into JSON mode, extracting "Sentiment Shifts" and "Psychological Safety Markers" alongside basic dialogue acts.
- Documented the completed Behavioral Metrics and Semantic NLP capabilities in `phase4_analysis.md`.

### August 7: TRIP Lab Stress Test
- Processed two `.mp4` video files from the TRIP Lab dataset.
- Validated the `behavioral_metrics.py` module, which successfully quantified cognitive load (51%+ silence ratios) and tracked hierarchical shifts across 6 distinct speakers.
- Validated the local Ollama NLP module (`dialogue_tagger.py`), which successfully extracted zero-shot psychological markers (e.g., identifying "Hedging" safety behaviors and "Anxious/Frustrated" sentiment shifts in real-time).

### August 11: Eleventh Meeting
- Met with mentors to review the Phase 4 stress tests on TRIP Lab data.
- Planned the final software deliverable: an interactive visualization dashboard and CSV exporter.

### August 12: Dashboard Implementation
- Built `dashboard.py` using Plotly Dash to instantly render the generated JSON metrics into an interactive UI.
- Implemented native CSV exporting in the pipeline to support traditional statistical analysis.

### August 15: Final Blog Post
- Drafted and refined the official GSoC technical blog post documenting the entire TCAMP architecture.
- Finalized the codebase and prepared for the official Pull Request handoff.
