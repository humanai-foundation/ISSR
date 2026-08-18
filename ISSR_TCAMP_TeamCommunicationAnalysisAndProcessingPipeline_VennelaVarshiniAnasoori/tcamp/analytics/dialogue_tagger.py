import json
import logging
import requests
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class OllamaDialogueTagger:
    """
    Local NLP tagging engine using Llama 3.2 via Ollama.
    Classifies transcript utterances into distinct dialogue acts.
    """
    
    def __init__(self, model_name: str = "llama3.2", host: str = "http://localhost:11434"):
        self.model_name = model_name
        self.api_url = f"{host}/api/generate"
        
    def _test_connection(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            response = requests.get(self.api_url.replace("/api/generate", "/api/tags"), timeout=2)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def _query_ollama(self, text: str) -> Dict[str, str]:
        """Query local Ollama instance for JSON semantic tags."""
        prompt = (
            f"Analyze the following utterance and classify it into three fields. Return ONLY a valid JSON object.\n"
            f"1. dialogue_act: strictly one of [Instruction, Question, Acknowledgment, Warning, Statement]\n"
            f"2. sentiment_shift: strictly one of [Positive, Neutral, Anxious, Frustrated]\n"
            f"3. psychological_safety: strictly one of [Safe, Hedging, Permission-Seeking]\n\n"
            f"Utterance: \"{text}\"\n"
            f"Output JSON Format: {{\"dialogue_act\": \"...\", \"sentiment_shift\": \"...\", \"psychological_safety\": \"...\"}}"
        )
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        
        default_resp = {
            "dialogue_act": "Unclassified",
            "sentiment_shift": "Unclassified",
            "psychological_safety": "Unclassified"
        }
        
        try:
            response = requests.post(self.api_url, json=payload, timeout=60)
            if response.status_code == 200:
                result_str = response.json().get("response", "").strip()
                try:
                    return json.loads(result_str)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON from Ollama: {result_str}")
                    return default_resp
            return default_resp
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ollama API error: {e}")
            return default_resp

    def process(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process the transcript segments and append a 'dialogue_act' tag.
        """
        if not segments:
            return []
            
        logger.info("Checking local Ollama connection...")
        if not self._test_connection():
            logger.warning("Ollama is not running on localhost:11434. Skipping dialogue tagging.")
            # Still return segments, just without tags or with Error tags
            return segments
            
        logger.info(f"running semantic NLP tagging on {len(segments)} segments...")
        
        tagged_segments = []
        for i, seg in enumerate(segments):
            tagged_seg = seg.copy()
            
            if not tagged_seg.get('text'):
                tagged_seg['dialogue_act'] = "Unclassified"
                tagged_seg['sentiment_shift'] = "Unclassified"
                tagged_seg['psychological_safety'] = "Unclassified"
            else:
                tags = self._query_ollama(tagged_seg['text'])
                tagged_seg['dialogue_act'] = tags.get('dialogue_act', 'Unclassified')
                tagged_seg['sentiment_shift'] = tags.get('sentiment_shift', 'Unclassified')
                tagged_seg['psychological_safety'] = tags.get('psychological_safety', 'Unclassified')
                
            if (i + 1) % 10 == 0:
                logger.info(f"Tagged {i + 1}/{len(segments)} segments...")
                
            tagged_segments.append(tagged_seg)
            
        logger.info("Dialogue Tagging complete.")
        return tagged_segments

    def save_report(self, tagged_segments: List[Dict[str, Any]], output_path: str):
        """Save tagged segments to a JSON file."""
        with open(output_path, 'w') as f:
            json.dump(tagged_segments, f, indent=4)
        logger.info(f"Saved Tagged Transcript to {output_path}")
