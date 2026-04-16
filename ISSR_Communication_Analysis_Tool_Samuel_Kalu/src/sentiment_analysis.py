# ===================================== ENFORCE CACHE DIRECTORY======================================
import os

os.environ["TORCH_HOME"] = "./model_weights/torch"
os.environ["HF_HOME"] = "./model_weights/huggingface"
os.environ["PYANNOTE_CACHE"] = "./model_weights/torch/pyannote"
# ====================================================================================================
import warnings

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

warnings.filterwarnings("ignore")

analyzer = SentimentIntensityAnalyzer()
hf_analyzer = None


def analyze_sentiment(text, use_hf=False):
    """Perform sentiment analysis using VADER and return a composite score from -1 to +1."""
    global hf_analyzer
    if use_hf:
        if hf_analyzer is None:
            from transformers import pipeline
            hf_analyzer = pipeline("sentiment-analysis")
        result = hf_analyzer(text)[0]
        label = result["label"].upper()
        confidence = float(result["score"])
        return confidence if label == "POSITIVE" else -confidence

    scores = analyzer.polarity_scores(text)
    return scores["compound"]
