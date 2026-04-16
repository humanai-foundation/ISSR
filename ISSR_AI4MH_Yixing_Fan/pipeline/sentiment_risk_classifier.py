import pandas as pd
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# 📦 Download VADER model if not already downloaded
try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    nltk.download("vader_lexicon")

# Step 1: Load filtered Reddit data
print("📥 Loading preprocessed Reddit posts...")
df = pd.read_csv("output/filtered_reddit_posts.csv")

# Use the correct column that contains Reddit post content
text_col = "cleaned_text"

# Step 2: Sentiment classification using VADER
print("🔍 Running sentiment analysis (VADER)...")
sia = SentimentIntensityAnalyzer()
hf_pipeline = None
textblob_analyzer = None

def classify_sentiment(text, use_textblob=False, use_huggingface=False):
    """Classify sentiment using VADER (default), TextBlob, or HuggingFace pipeline."""
    global hf_pipeline, textblob_analyzer

    if use_huggingface:
        if hf_pipeline is None:
            from transformers import pipeline
            hf_pipeline = pipeline("sentiment-analysis", truncation=True, max_length=512)
        result = hf_pipeline(str(text))[0]
        label = result["label"].lower()
        if "pos" in label:
            return "Positive"
        elif "neg" in label:
            return "Negative"
        else:
            return "Neutral"

    if use_textblob:
        if textblob_analyzer is None:
            from textblob import TextBlob
            textblob_analyzer = TextBlob
        polarity = textblob_analyzer(str(text)).sentiment.polarity
        if polarity > 0.1:
            return "Positive"
        elif polarity < -0.1:
            return "Negative"
        else:
            return "Neutral"

    # Default: VADER
    score = sia.polarity_scores(text)['compound']
    if score >= 0.3:
        return "Positive"
    elif score <= -0.3:
        return "Negative"
    else:
        return "Neutral"

df['sentiment'] = df[text_col].astype(str).apply(classify_sentiment)

# Step 3: Risk level detection using expanded keyword sets
print("🚨 Assessing risk levels using keyword matching...")

high_risk_keywords = [
    "end it", "unalive", "kill myself", "disappear", "suicide", 
    "can't go on", "i'm done", "give up", "sleep forever", 
    "worthless", "hopeless", "kms", "no one would care", "void", "spiraling"
]

moderate_risk_keywords = [
    "feel lost", "need help", "relapse", "panic", "empty", 
    "depressed", "struggling", "overwhelmed", "can't sleep", "numb"
]

def classify_risk(text):
    """Assign risk level based on presence of emotional language."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in high_risk_keywords):
        return "High-Risk"
    elif any(kw in text_lower for kw in moderate_risk_keywords):
        return "Moderate Concern"
    else:
        return "Low Concern"

df['risk_level'] = df[text_col].astype(str).apply(classify_risk)

# Step 4: Export results
output_path = "output/sentiment_risk_classified.csv"
df.to_csv(output_path, index=False)
print(f"✅ Classification complete. File saved to: {output_path}")
