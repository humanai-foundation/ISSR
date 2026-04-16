# pipeline/fetch_reddit.py

import os
import praw
import pandas as pd
import re
import emoji
import nltk
from nltk.corpus import stopwords
from dotenv import load_dotenv

nltk.download('stopwords')
stop_words = set(stopwords.words('english'))

# ========== Load credentials ==========
load_dotenv()

reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD")
)

# ========== Define keywords and subreddits ==========
keywords = [
    "depressed", "suicidal", "addiction help", "mental breakdown", "self harm",
    "overwhelmed", "relapse", "panic attack", "feel hopeless", "i want to die",
    "lost will", "crying all night", "emotional numbness", "can't go on", "need therapy",
    "anxiety attack", "feeling empty", "burnout", "mental exhaustion", "can't sleep",
    "constant worry", "feeling worthless", "no motivation", "social isolation", "panic disorder",
    "intrusive thoughts", "emotional pain", "mental fog", "dissociation", "feeling trapped",
    "racing thoughts", "mood swings", "emotional breakdown", "mental health crisis", "therapy needed" , "feel like a burden" ,"nobody cares about me"
]

subreddits = [
    "depression", "SuicideWatch", "mentalhealth", "Anxiety", "addiction", "offmychest",
    "sad", "mentalillness", "PTSD", "BPD", "depersonalization", "lonely", "grief", "socialanxiety",
    "mentalhealthsupport", "CPTSD", "OCD", "ADHD", "AnxietyDepression", "mentalhealthrecovery",
    "mentalhealthawareness", "bipolar", "traumatoolbox", "mentalhealthmemes", "mentalhealthart",
    "mentalhealthvideos", "mentalhealthresources", "mentalhealthadvice", "mentalhealthstories",
    "mentalhealthchat", "mentalhealthhelp", "mentalhealthcommunity",
    "mentalhealthmatters", "mentalhealthwarriors","healthanxiety" ,"KindVoice"
]

# ========== Preprocessing function ==========
def clean_text(text):
    text = text.lower()
    text = ' '.join(word for word in text.split() if word not in stop_words)
    return text

# ========== Main function ==========
def main():
    posts = []

    for sub in subreddits:
        print(f"📥 Fetching from r/{sub}...")
        try:
            for post in reddit.subreddit(sub).hot(limit=100):
                raw_text = (post.title or "") + " " + (post.selftext or "")
                if any(kw in raw_text.lower() for kw in keywords):
                    posts.append({
                        "id": post.id,
                        "timestamp": post.created_utc,
                        "subreddit": sub,
                        "raw_text": raw_text,
                        "cleaned_text": clean_text(raw_text),
                        "upvotes": post.score,
                        "comments": post.num_comments,
                        "url": post.url
                    })
        except Exception as e:
            print(f"⚠️ Error with r/{sub}: {e}")

    df = pd.DataFrame(posts)
    os.makedirs("output", exist_ok=True)
    df.to_csv("output/filtered_reddit_posts.csv", index=False)
    print(f"✅ Saved {len(df)} posts to output/filtered_reddit_posts.csv")

if __name__ == "__main__":
    main()
