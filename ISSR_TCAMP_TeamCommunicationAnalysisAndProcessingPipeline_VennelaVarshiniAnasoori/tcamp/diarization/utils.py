import json
from typing import Dict, Any, List

def save_diarization_results(results: List[Dict[str, Any]], output_path: str):
    """
    Save the diarization output to a JSON file.
    
    Args:
        results: List containing the diarization segments.
        output_path: Path to save the JSON file.
    """
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=4)

def save_rttm(results: List[Dict[str, Any]], output_path: str, uri: str = "audio"):
    """
    Save the diarization output to a standard RTTM file.
    """
    with open(output_path, 'w') as f:
        for seg in results:
            speaker = seg['speaker']
            start = seg['start']
            duration = seg['end'] - start
            # Format: SPEAKER <uri> 1 <start> <duration> <NA> <NA> <speaker> <NA> <NA>
            f.write(f"SPEAKER {uri} 1 {start:.3f} {duration:.3f} <NA> <NA> {speaker} <NA> <NA>\n")
        
def load_diarization_results(input_path: str) -> List[Dict[str, Any]]:
    """
    Load a previously saved diarization JSON file.
    """
    with open(input_path, 'r') as f:
        return json.load(f)

def parse_rttm(rttm_path: str) -> List[Dict[str, Any]]:
    """
    Parse an RTTM file (commonly used for diarization evaluation).
    
    Args:
        rttm_path: Path to the RTTM file.
        
    Returns:
        List of segment dictionaries.
    """
    segments = []
    with open(rttm_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 8 and parts[0] == "SPEAKER":
                # SPEAKER file 1 start duration <NA> <NA> speaker <NA> <NA>
                start = float(parts[3])
                duration = float(parts[4])
                speaker = parts[7]
                segments.append({
                    "start": start,
                    "end": start + duration,
                    "speaker": speaker
                })
    return segments

def segments_to_annotation(segments: List[Dict[str, Any]], uri: str = "audio") -> Any:
    """
    Convert a list of segment dictionaries to a pyannote.core.Annotation object.
    Requires pyannote.core to be installed.
    """
    try:
        from pyannote.core import Annotation, Segment  # type: ignore
    except ImportError:
        raise ImportError("Please install pyannote.core (usually comes with pyannote.audio)")
        
    annotation = Annotation(uri=uri)
    for seg in segments:
        annotation[Segment(seg["start"], seg["end"])] = seg["speaker"]
    return annotation

def calculate_der(reference_segments: List[Dict[str, Any]], hypothesis_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate the Diarization Error Rate (DER) between reference (ground truth) and hypothesis (prediction).
    
    Args:
        reference_segments: Ground truth segments
        hypothesis_segments: Predicted segments from pipeline
        
    Returns:
        Dict: Detailed metrics including overall DER, miss, false alarm, and confusion rates.
    """
    try:
        from pyannote.metrics.diarization import DiarizationErrorRate  # type: ignore
    except ImportError:
        raise ImportError("Please install pyannote.metrics to calculate DER")
        
    reference = segments_to_annotation(reference_segments, uri="eval")
    hypothesis = segments_to_annotation(hypothesis_segments, uri="eval")
    
    metric = DiarizationErrorRate()
    der_val = metric(reference, hypothesis)
    components = metric.compute_components(reference, hypothesis)
    
    total = max(components.get("total", 1.0), 1e-6)
    
    return {
        "der": abs(der_val),
        "miss": components.get("missed detection", 0.0) / total,
        "false_alarm": components.get("false alarm", 0.0) / total,
        "confusion": components.get("confusion", 0.0) / total,
        "total_speech_duration": total
    }
