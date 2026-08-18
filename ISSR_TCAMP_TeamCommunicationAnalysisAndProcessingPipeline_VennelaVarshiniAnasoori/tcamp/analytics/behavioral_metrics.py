import json
import logging
# pyrefly: ignore [missing-import]
import numpy as np
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class BehavioralAnalytics:
    """
    Extracts 6 core behavioral metrics from timestamped transcripts.
    1. Total Talk Time
    2. Silence Ratio
    3. Turn-Taking Rate
    4. Interruptions (Overlaps)
    5. Response Latency
    6. Centralization (Gini Coefficient)
    """
    
    def __init__(self):
        pass
        
    def _calculate_gini(self, values: List[float]) -> float:
        """Calculate Gini coefficient of a list of values."""
        if not values or sum(values) == 0:
            return 0.0
        v = sorted(values)
        n = len(v)
        index = np.arange(1, n + 1)
        return float((np.sum((2 * index - n  - 1) * v)) / (n * np.sum(v)))

    def _union_of_intervals(self, segments: List[Dict[str, Any]]) -> float:
        """Calculate total non-overlapping speech duration."""
        if not segments:
            return 0.0
        
        # Sort by start time
        sorted_segs = sorted(segments, key=lambda x: x['start'])
        
        total_duration = 0.0
        current_start = sorted_segs[0]['start']
        current_end = sorted_segs[0]['end']
        
        for seg in sorted_segs[1:]:
            if seg['start'] <= current_end:
                current_end = max(current_end, seg['end'])
            else:
                total_duration += (current_end - current_start)
                current_start = seg['start']
                current_end = seg['end']
                
        total_duration += (current_end - current_start)
        return total_duration

    def process(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process the transcript segments to generate behavioral metrics.
        segments format: [{'start': 0.0, 'end': 1.0, 'speaker': 'SPEAKER_00', 'text': '...'}]
        """
        if not segments:
            return {}
            
        logger.info(f"Extracting Behavioral Metrics from {len(segments)} segments...")
        
        sorted_segs = sorted(segments, key=lambda x: x['start'])
        meeting_start = sorted_segs[0]['start']
        meeting_end = max([s['end'] for s in sorted_segs])
        meeting_duration = meeting_end - meeting_start
        meeting_duration_minutes = meeting_duration / 60.0 if meeting_duration > 0 else 1.0
        
        # 1. Total Talk Time
        talk_times = {}
        for seg in segments:
            speaker = seg['speaker']
            duration = seg['end'] - seg['start']
            talk_times[speaker] = talk_times.get(speaker, 0.0) + duration
            
        # 2. Silence Ratio
        total_speech_time = self._union_of_intervals(segments)
        silence_ratio = (meeting_duration - total_speech_time) / meeting_duration if meeting_duration > 0 else 0.0
        
        # 3, 4, 5. Turn-Taking, Interruptions, Response Latency
        speaker_changes = 0
        interruptions = 0
        latencies = []
        
        for i in range(1, len(sorted_segs)):
            prev_seg = sorted_segs[i-1]
            curr_seg = sorted_segs[i]
            
            if prev_seg['speaker'] != curr_seg['speaker']:
                speaker_changes += 1
                
                gap = curr_seg['start'] - prev_seg['end']
                if gap < 0:
                    interruptions += 1
                elif gap > 0:
                    latencies.append(gap)
                    
        turn_taking_rate = speaker_changes / meeting_duration_minutes
        avg_response_latency = float(np.mean(latencies)) if latencies else 0.0
        
        # 6. Centralization (Gini)
        gini = self._calculate_gini(list(talk_times.values()))
        
        metrics = {
            "meeting_duration_seconds": round(meeting_duration, 2),
            "total_talk_time_by_speaker": {k: round(v, 2) for k, v in talk_times.items()},
            "silence_ratio": round(silence_ratio, 3),
            "turn_taking_rate_per_min": round(turn_taking_rate, 2),
            "interruptions": interruptions,
            "average_response_latency_seconds": round(avg_response_latency, 2),
            "centralization_gini": round(gini, 3)
        }
        
        return metrics

    def save_report(self, metrics: Dict[str, Any], output_path: str):
        """Save metrics to a JSON report."""
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=4)
        logger.info(f"saved behavioral metrics to {output_path}")
