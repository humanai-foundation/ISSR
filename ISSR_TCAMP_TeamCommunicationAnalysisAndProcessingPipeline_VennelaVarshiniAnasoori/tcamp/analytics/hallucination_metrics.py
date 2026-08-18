import os
import re
import sys
import glob
import logging
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Fix console encoding on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

TRANSCRIPTS_DIR = os.path.join("observations", "outputs")

# Classify text as a hallucination based on known Whisper heuristics.
KNOWN_EXACT_HALLUCINATIONS = {
    "you", "you.", "you!", "you?", "you...",
    "i'm", "i'm.", "i'm...",
    "[unintelligible]", "[silence]", "(music)",
    "what?", "what.",
}

KNOWN_SUBSTRING_HALLUCINATIONS = [
    "thank you for watching", "subs by", "www.", "http", "amara.org",
    "zeoranger", "subtitles", "thank you.", "thank you!"
]

def is_hallucination(text, duration):
    text_lower = text.strip().lower()
    
    # Check exact matches against typical silence artifacts.
    if text_lower in KNOWN_EXACT_HALLUCINATIONS:
        return True
        
    # Check substrings
    for sub in KNOWN_SUBSTRING_HALLUCINATIONS:
        if sub in text_lower:
            # 'thank you' is context-dependent based on segment duration.
            if sub in ["thank you.", "thank you!"] and duration > 1.5:
                continue
            return True
            
    # Filter anomalous short durations.
    if duration <= 0.1 and len(text_lower.split()) <= 2:
        if text_lower not in ["yeah", "yeah.", "ok", "ok.", "okay", "okay."]:
            return True
            
    return False

def analyze_transcripts():
    files = glob.glob(os.path.join(TRANSCRIPTS_DIR, "transcript_*.txt"))
    
    if not files:
        logger.warning("No transcripts found in outputs directory.")
        return
        
    total_meetings = len(files)
    all_hallucinations = Counter()
    total_segments_all = 0
    total_hallucinations_all = 0
    
    # Time context counters
    context_stats = {
        "isolated_silence": 0, # Gap before > 2s AND gap after > 2s
        "trailing_speech": 0,  # Gap before < 2s AND gap after > 2s
        "leading_speech": 0,   # Gap before > 2s AND gap after < 2s
        "mid_speech": 0        # Gap before < 2s AND gap after < 2s
    }

    logger.info("Initializing Transcription Anomaly Scanner...")
    logger.info(f"Scanning {total_meetings} meetings.")
    
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        segments = []
        pattern = re.compile(r'\[(\d+\.\d+) - (\d+\.\d+)\] (SPEAKER_\w+) \((RAW|DFN)\): (.*)')
        
        for line in lines:
            # Strip optional line number prefixes
            line = re.sub(r'^\d+:\s+', '', line)
            
            match = pattern.match(line.strip())
            if match:
                start = float(match.group(1))
                end = float(match.group(2))
                speaker = match.group(3)
                source = match.group(4)
                text = match.group(5)
                duration = end - start
                
                segments.append({
                    "start": start,
                    "end": end,
                    "duration": duration,
                    "speaker": speaker,
                    "text": text,
                    "is_hallucination": is_hallucination(text, duration)
                })
        
        file_total = len(segments)
        total_segments_all += file_total
        file_hallucinations = 0
        
        for i, seg in enumerate(segments):
            if seg["is_hallucination"]:
                file_hallucinations += 1
                total_hallucinations_all += 1
                all_hallucinations[seg["text"].strip()] += 1
                
                # Analyze time context
                gap_before = 999.0
                gap_after = 999.0
                
                if i > 0:
                    gap_before = seg["start"] - segments[i-1]["end"]
                if i < len(segments) - 1:
                    gap_after = segments[i+1]["start"] - seg["end"]
                    
                if gap_before > 2.0 and gap_after > 2.0:
                    context_stats["isolated_silence"] += 1
                elif gap_before <= 2.0 and gap_after > 2.0:
                    context_stats["trailing_speech"] += 1
                elif gap_before > 2.0 and gap_after <= 2.0:
                    context_stats["leading_speech"] += 1
                else:
                    context_stats["mid_speech"] += 1
                    
        percent = (file_hallucinations / file_total * 100) if file_total > 0 else 0
        logger.info(f"{os.path.basename(file)}: {file_hallucinations}/{file_total} anomalies ({percent:.2f}%)")
        
    logger.info("--- Aggregate Statistics ---")
    logger.info(f"Total Segments Across All Meetings: {total_segments_all}")
    logger.info(f"Total Hallucinations: {total_hallucinations_all}")
    if total_segments_all > 0:
        logger.info(f"Overall Hallucination Rate: {(total_hallucinations_all / total_segments_all * 100):.2f}%")
        
    logger.info("--- Most Common Anomalies ---")
    for phrase, count in all_hallucinations.most_common(10):
        logger.info(f"  {count}x : '{phrase}'")
        
    logger.info("--- Temporal Context ---")
    logger.info(f"  Isolated Silence: {context_stats['isolated_silence']}")
    logger.info(f"  Trailing Speech: {context_stats['trailing_speech']}")
    logger.info(f"  Leading Speech: {context_stats['leading_speech']}")
    logger.info(f"  Mid-Speech: {context_stats['mid_speech']}")

if __name__ == "__main__":
    analyze_transcripts()
