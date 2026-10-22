import os
import time
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# Default local weights path
DEFAULT_MODEL_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "results", "xlm_roberta_system1")
)

INTENSITY_MAP = {
    0: {
        "name": "Level 0: Safe",
        "description": "Neutral or positive sentiment; no suicidal ideation or acute distress detected.",
        "is_crisis": False,
        "action": "Standard logging / routine engagement."
    },
    1: {
        "name": "Level 1: Mild Distress / Anxiety",
        "description": "Mild emotional distress, stress, or anxiety without expressed intent of self-harm.",
        "is_crisis": False,
        "action": "Provide supportive, empathetic resources and stress-relief guidance."
    },
    2: {
        "name": "Level 2: Moderate / Severe Depression",
        "description": "Substantial depressive feelings, hopelessness, or passive distress.",
        "is_crisis": True,
        "action": "Route to compassionate support agent; offer counseling and hotline contact info."
    },
    3: {
        "name": "Level 3: Acute Crisis",
        "description": "Immediate suicidal ideation, expressed intent, or acute crisis keywords.",
        "is_crisis": True,
        "action": "URGENT INTERVENTION: Trigger immediate emergency safety protocols & Crisis Lifeline (988)."
    }
}

class System1CrisisGatekeeper:
    """
    Non-Autoregressive Multilingual System 1 Crisis Gatekeeper.
    Performs single-pass sequence classification across 4 intensity levels
    with sub-50ms latency.
    """
    def __init__(self, model_path: str = DEFAULT_MODEL_DIR, device: str = None):
        self.model_path = model_path
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Model directory '{self.model_path}' not found.\n"
                f"Please ensure the fine-tuned XLM-RoBERTa model weights are downloaded to this path."
            )
        
        has_weights = any(
            os.path.exists(os.path.join(self.model_path, w))
            for w in ("model.safetensors", "pytorch_model.bin")
        )
        if not has_weights:
            raise FileNotFoundError(
                f"No model weight file ('model.safetensors' or 'pytorch_model.bin') found in '{self.model_path}'.\n"
                f"Please download the trained weights archive (e.g. from Kaggle/release) into '{self.model_path}'."
            )

        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        print(f"[System 1] Loading tokenizer from: {self.model_path}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        
        print(f"[System 1] Loading model backbone on {self.device}...")
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_path)
        self.model.to(self.device)
        self.model.eval()
        print("[System 1] Gatekeeper initialized and ready for real-time triage.")

    def predict(self, text: str) -> dict:
        """
        Evaluate text input and return intensity level, confidence, and metadata.
        """
        start_time = time.perf_counter()
        
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=128
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)[0].cpu().numpy()
            pred_idx = int(torch.argmax(logits, dim=-1).item())

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        meta = INTENSITY_MAP[pred_idx]

        return {
            "text": text,
            "intensity_level": pred_idx,
            "intensity_name": meta["name"],
            "description": meta["description"],
            "is_crisis": meta["is_crisis"],
            "confidence": float(probs[pred_idx]),
            "suggested_action": meta["action"],
            "latency_ms": round(latency_ms, 2),
            "probabilities": {
                "Level 0 (Safe)": round(float(probs[0]), 4),
                "Level 1 (Anxiety / Mild)": round(float(probs[1]), 4),
                "Level 2 (Depression / Moderate)": round(float(probs[2]), 4),
                "Level 3 (Acute Crisis)": round(float(probs[3]), 4)
            }
        }

if __name__ == "__main__":
    gatekeeper = System1CrisisGatekeeper()
    test_samples = [
        "I just watched a movie and had dinner with my family.",
        "I feel really overwhelmed with work and feel nervous all the time.",
        "Nothing seems to get better, I am feeling empty and completely depressed.",
        "I can't go on living anymore, I just want to end it tonight."
    ]
    print("\n--- Running System 1 Verification Suite ---")
    for sample in test_samples:
        res = gatekeeper.predict(sample)
        print(f"\nText: \"{res['text']}\"")
        print(f" -> Level: {res['intensity_level']} ({res['intensity_name']}) | Confidence: {res['confidence']:.1%} | Latency: {res['latency_ms']} ms")
        print(f" -> Action: {res['suggested_action']}")
