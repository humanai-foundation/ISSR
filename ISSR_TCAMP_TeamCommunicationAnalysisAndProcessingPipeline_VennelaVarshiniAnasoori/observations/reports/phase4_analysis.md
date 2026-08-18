# Phase 4: Communication Analytics Engine

---

This document summarizes the development and implementation of the Phase 4 Behavioral Analytics Engine. The goal of this phase was to transition from pure speech-to-text processing into the extraction of meaningful, quantifiable psychological metrics. 

## Part 1: Mathematical Signal Processing (`behavioral_metrics.py`)
This module uses Python and NumPy to extract foundational, timing-based behavioral metrics directly from the diarized transcript.

**Implemented Metrics:**
1. **Total Talk Time:** Measures the sheer volume of speech per person to detect baseline dominance.
2. **Silence Ratio:** Calculates the percentage of the meeting with absolutely no speech, serving as an indicator of cognitive load or tension.
3. **Turn-Taking Rate:** Tracks how frequently the conversational floor is passed between team members.
4. **Turn-Taking Gini Coefficient:** Mathematically measures the equality of voice distribution (0 = perfectly equal, 1 = perfectly unequal). High inequality signals hidden hierarchies or autocratic leadership styles.
5. **Interruption and Overlap Ratios:** Maps conversational dominance, assertiveness, and status contestation by tracking when a speaker cuts another speaker off in real-time.
6. **Latency of Response:** Measures the duration of silence before a team member replies to a prompt, reflecting hesitation, social alignment, or cognitive load.

## Part 2: Semantic NLP Tagging (`dialogue_tagger.py`)
Because mathematical metrics cannot detect *intent*, we implemented a zero-shot NLP engine. It passes the final transcript to a local Llama 3.2 instance (via Ollama) running strictly in JSON Mode. 

The LLM analyzes the semantic structure of every utterance and outputs three structured fields for qualitative analysis:

**Implemented Semantic Tags:**
1. **Dialogue Acts:** Classifies utterances as *Instruction, Question, Acknowledgment, Warning, or Statement* to identify technical leadership and filter out conversational backchanneling.
2. **Sentiment Shifts:** Maps the emotional tone as *Positive, Neutral, Anxious, or Frustrated* over time to isolate exact mission triggers that degrade team affective states.
3. **Psychological Safety Markers:** Scans transcripts for *Hedging* or *Permission-Seeking* language to measure self-censorship and psychological safety.

---

## Part 3: TRIP Lab Sample Validation
To ensure the pipeline is ready for production, the entire system was deployed to a Google Colab GPU environment to process two large, multi-speaker `.mp4` clinical samples from the TRIP Lab (`Experimenter_CREW_999`).

### Validation Results
1. **Audio Extraction:** The pipeline utilized `ffmpeg` to extract the audio track directly from the video files, passing them into the DeepFilterNet enhancement suite.
2. **Behavioral Metrics Scaling:** The `behavioral_metrics.py` module scaled effectively. On the 6-speaker sample, it quantified cognitive load (calculating a 51.3% silence ratio) and mapped team dynamics (tracking 15 interruptions). 
3. **Semantic Detection:** The local Llama 3.2 Ollama module detected psychological markers within the text. During the test, it isolated safety and sentiment shifts. For example:
   - *Example 1:* When a speaker said *"But it's not. Was it? I think that was it,"* the model tagged the utterance as **`Anxious`** (Sentiment) and **`Hedging`** (Safety Marker).
   - *Example 2:* When a speaker hesitated with filler words *"Um, noise, uh, chalk,"* the model recognized the uncertainty and flagged it as **`Hedging`**.

