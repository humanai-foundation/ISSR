import os
import pandas as pd
from transformers import pipeline
import torch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Choose device: use GPU if available, otherwise use CPU
device = 0 if torch.cuda.is_available() else -1
print(f"Using device: {'cuda' if device == 0 else 'cpu'}")

# Load the CSV file
input_path = os.path.join(OUTPUT_DIR, "filtered_reddit_posts.csv")
df = pd.read_csv(input_path)

# Get the 'cleaned_text' column, drop any blank or missing values, and convert to string
texts = df["cleaned_text"].dropna()
texts = texts[texts.str.strip() != ""].astype(str).tolist()[:200]  # Limit to first 200 for speed

# Load the pre-trained sentiment analysis model from Hugging Face (fine-tuned on SST-2)
classifier = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english", device=device)

# Apply the sentiment model to each text
results = classifier(texts, truncation=True)

# Add the predictions back into a copy of the DataFrame
df_result = df.iloc[:len(results)].copy()
df_result["sentiment_label"] = [r["label"] for r in results]     # 'POSITIVE' or 'NEGATIVE'
df_result["sentiment_score"] = [r["score"] for r in results]     # Confidence score

# Save the result to a new CSV file
output_csv = os.path.join(OUTPUT_DIR, "bert_sentiment_result.csv")
df_result.to_csv(output_csv, index=False)
print(f"Saved to {output_csv} ✅")
