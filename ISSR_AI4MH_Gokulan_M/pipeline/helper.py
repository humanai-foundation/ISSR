import numpy as np
import praw
import re
import os
from dotenv import load_dotenv
import pandas as pd
import pandas as pd
from nltk.corpus import stopwords
import nltk
from pipeline.keywords import keywords


load_dotenv()

client_id=os.getenv('CLIENT_ID')
client_secret=os.getenv('CLIENT_SECRET')
username=os.getenv('USER_NAME')
password=os.getenv('PASSWORD')
user_agent=os.getenv('USER_AGENT')


reddit=praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    user_agent=user_agent,
    username=username,
    password=password
)

subreddits = [
    # Mental Health
    "mentalhealth",          
    "depression_help",

    # Suicidal
    "offmychest",
    "suicidewatch",

    # Substance Use    
    "Drugs",         
    "addiction" 
]
nltk.download('stopwords')
STOPWORDS= set(stopwords.words('english'))

def extract_reddit_posts(limit=100):
    posts_data = []
    try: 
        for subreddit_name in subreddits:
            print(f"Fetching posts from r/{subreddit_name}...")
            subreddit = reddit.subreddit(subreddit_name)

            for post in subreddit.new(limit=limit):
                timestamp=post.created_utc
                timestamp=pd.to_datetime(timestamp,unit='s')
                if any(keyword.lower() in post.title.lower() + post.selftext.lower() for keyword in keywords):
                    posts_data.append([
                        post.id,
                        str(post.author),
                        post.created_utc,
                        post.title,
                        post.selftext,
                        post.score,
                        post.num_comments
                    ])
        
        columns=['post_id', 'username','timestamp','title','content','upvotes','comments']
        df=pd.DataFrame(posts_data, columns=columns)
        
        return df
    
    except Exception as e:
        print("An error occured: ",e)


def preprocess_text(text):

    text = text.lower()
    text = re.sub(r'http\S+', '', text)                                      # Remove URLs
    text = re.sub(r'[^a-zA-Z\s]', '', text)                                  # Remove special characters
    text = re.sub(r'\d+', '', text)                                          # Remove numbers
    text = ' '.join(word for word in text.split() if word not in STOPWORDS)  # Remove stopwords

    return text