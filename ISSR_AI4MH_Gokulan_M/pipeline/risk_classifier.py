from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

risk_labels= ['High Risk', 'Low Risk', 'Moderate Risk']   

import torch
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

risk_labels = [
    "High Risk",
    "Low Risk",
    "Moderate Risk"
]


MODEL_NAME = "gokulan006/distilbert-reddit-mental-health-risk-classifier"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)


def predict_risk_level(text):
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=128
    )

    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    probabilities = torch.softmax(
        outputs.logits,
        dim=1
    )

    predicted_class = torch.argmax(
        probabilities,
        dim=1
    ).item()
 
    return risk_labels[predicted_class]
         
 
analyser = SentimentIntensityAnalyzer()

def sentiment_scores(sentence):

    if isinstance(sentence, float):
        sentence = str(sentence)
    
    sentence_dict = analyser.polarity_scores(sentence)

    if sentence_dict['compound'] >=0.10:
        return 'Positive'
    elif sentence_dict['compound'] <=-0.10:
        return 'Negative'
    else:
        return 'Neutral'
    