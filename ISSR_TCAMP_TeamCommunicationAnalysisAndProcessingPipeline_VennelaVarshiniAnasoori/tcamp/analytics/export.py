import csv
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def export_metrics_to_csv(metrics_data: Dict[str, Any], output_csv_path: str | Path):
    """
    Exports behavioral metrics into a flat CSV format for external statistical analysis.
    """
    output_csv_path = Path(output_csv_path)
    
    # Flatten talk times
    talk_times = metrics_data.get("total_talk_time_by_speaker", {})
    
    # Base fields
    flat_data = {
        "meeting_duration_seconds": metrics_data.get("meeting_duration_seconds", 0.0),
        "silence_ratio": metrics_data.get("silence_ratio", 0.0),
        "turn_taking_rate_per_min": metrics_data.get("turn_taking_rate_per_min", 0.0),
        "interruptions": metrics_data.get("interruptions", 0),
        "average_response_latency_seconds": metrics_data.get("average_response_latency_seconds", 0.0),
        "centralization_gini": metrics_data.get("centralization_gini", 0.0)
    }
    
    # Add dynamic speaker columns
    for speaker, time in talk_times.items():
        flat_data[f"talk_time_{speaker}"] = time

    headers = list(flat_data.keys())
    
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerow(flat_data)
        
    logger.info(f"Saved metrics CSV to {output_csv_path}")


def export_transcript_to_csv(transcript_data: List[Dict[str, Any]], output_csv_path: str | Path):
    """
    Converts the tagged transcript JSON into a flat CSV, where each row is an utterance.
    """
    output_csv_path = Path(output_csv_path)
    
    if not transcript_data:
        logger.warning(f"No transcript data to export to {output_csv_path}")
        return

    # Determine headers based on the first segment (assuming uniform keys)
    # Standard keys: start, end, speaker, text, dialogue_act, sentiment_shift, psychological_safety
    headers = [
        "segment_id", "speaker", "start_time", "end_time", "duration", 
        "text", "dialogue_act", "sentiment_shift", "psychological_safety"
    ]
    
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        
        for i, seg in enumerate(transcript_data):
            row = {
                "segment_id": i,
                "speaker": seg.get("speaker", "UNKNOWN"),
                "start_time": seg.get("start", 0.0),
                "end_time": seg.get("end", 0.0),
                "duration": round(seg.get("end", 0.0) - seg.get("start", 0.0), 3),
                "text": seg.get("text", "").strip(),
                "dialogue_act": seg.get("dialogue_act", "Unclassified"),
                "sentiment_shift": seg.get("sentiment_shift", "Unclassified"),
                "psychological_safety": seg.get("psychological_safety", "Unclassified")
            }
            writer.writerow(row)
            
    logger.info(f"Saved transcript CSV to {output_csv_path}")
