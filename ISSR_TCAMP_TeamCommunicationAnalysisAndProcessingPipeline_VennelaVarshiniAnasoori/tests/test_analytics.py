import re
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add project root to sys.path so we can import tcamp modules
sys.path.append(str(Path(__file__).parent.parent))

from tcamp.analytics.behavioral_metrics import BehavioralAnalytics
from tcamp.analytics.dialogue_tagger import OllamaDialogueTagger

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_transcript(file_path: Path) -> List[Dict[str, Any]]:
    """
    Parses a text transcript into structured segment dictionaries.
    
    Args:
        file_path: Path to the transcript text file.
        
    Returns:
        List of dictionaries containing start, end, speaker, and text.
    """
    segments: List[Dict[str, Any]] = []
    # Pattern to match: [023.0 - 024.8] SPEAKER_01 (DFN): Microphones with your right.
    pattern = re.compile(r'\[(\d+\.\d+) - (\d+\.\d+)\] (SPEAKER_\d+).+?: (.+)')
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                start = float(match.group(1))
                end = float(match.group(2))
                speaker = match.group(3)
                text = match.group(4)
                
                segments.append({
                    "start": start,
                    "end": end,
                    "speaker": speaker,
                    "text": text
                })
    return segments

def main() -> None:
    """Validates analytics and tagging modules."""
    if len(sys.argv) > 1:
        transcript_path = Path(sys.argv[1])
    else:
        transcript_path = Path("observations/hallucination_experiments/transcript_EN2002a_medium.en.txt")
        
    if not transcript_path.exists():
        logger.error(f"Could not find {transcript_path}")
        return
        
    logger.info(f"Processing {transcript_path}...")
    segments = parse_transcript(transcript_path)
    logger.info(f"Parsed {len(segments)} segments.")
    
    # Base name for output files
    base_name = transcript_path.stem.replace("transcript_", "")
    
    # Test Behavioral Metrics
    logger.info("validating behavioral metrics...")
    analytics = BehavioralAnalytics()
    metrics = analytics.process(segments)
    
    logger.info("\n" + json.dumps(metrics, indent=2))
    
    metrics_out = transcript_path.parent / f"test_behavioral_metrics_{base_name}.json"
    analytics.save_report(metrics, str(metrics_out))
    
    # Test Ollama Dialogue Tagger
    logger.info("validating semantic dialogue tagger...")
    tagger = OllamaDialogueTagger()
    tagged_segments = tagger.process(segments)
    
    if tagged_segments:
        tagged_out = transcript_path.parent / f"test_tagged_transcript_{base_name}.json"
        tagger.save_report(tagged_segments, str(tagged_out))
        logger.info(f"Saved full tagged transcript to {tagged_out}")
        
        logger.info("Sample of 5 tagged segments:")
        for seg in tagged_segments[:5]:
            logger.info(f"{seg['speaker']}: {seg['text']}  ->  [{seg.get('dialogue_act', 'None')}]")
            
if __name__ == "__main__":
    main()
