import pandas as pd
import os

from flask import Flask, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy

from pipeline.risk_classifier import predict_risk_level, sentiment_scores, analyser
from pipeline.location_extractor import get_coordinates
from pipeline.helper import extract_reddit_posts, preprocess_text

import time
from tqdm import tqdm
tqdm.pandas()
import warnings
warnings.filterwarnings('ignore')


app= Flask(__name__)
db_path=os.path.join(os.path.abspath(os.path.dirname(__file__)),'posts.db')
app.config['SQLALCHEMY_DATABASE_URI']= 'sqlite:///' + db_path  
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class RedditPosts(db.Model):
    __tablename__ = 'reddit_posts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime , nullable=False)
    content = db.Column(db.Text)
    upvotes = db.Column(db.Integer)
    comments = db.Column(db.Integer)
    sentiment = db.Column(db.String(50))
    risk_level = db.Column(db.String(50))

class PostLocations(db.Model):
    __tablename__= 'locations'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False)
    risk_level = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float(), nullable=False)
    longitude = db.Column(db.Float(), nullable=False)

class UserBehavior(db.Model):
    __tablename__ = 'Users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False)
    post_count = db.Column(db.Integer, default=0)
    high_risk_count = db.Column(db.Integer, default=0)
    sentiment_trend = db.Column(db.Float(), default=0.0)
    timestamp = db.Column(db.DateTime, nullable=False)

with app.app_context():
    db.create_all()
 

def store_df_in_sql(df):
    with app.app_context():
        for _,row in df.iterrows():
            post_exists = RedditPosts.query.filter_by(post_id=row['post_id']).first()

            if not post_exists:
                post = RedditPosts(
                    post_id=row['post_id'],
                    username=str(row['username']),
                    timestamp=row['timestamp'],
                    content=row['content'],
                    upvotes=row['upvotes'],
                    comments=row['comments'],
                    sentiment=row['sentiment'],
                    risk_level=row['risk_level']
                )
                db.session.add(post)
        
        db.session.commit()


def update_user_behavior(post_id, username, content, risk_level, timestamp):
    with app.app_context():
         
        try:
            user = UserBehavior.query.filter_by(username=str(username)).first()
            post = RedditPosts.query.filter_by(post_id=post_id).first()

            if user and not post:
                user.post_count +=1
                if risk_level == 'High Risk':
                    user.high_risk_count +=1
                content=str(content)
                sentiment_score=analyser.polarity_scores(content)['compound']
                user.sentiment_trend = (user.sentiment_trend + sentiment_score)/2
                user.timestamp=timestamp
                
            elif not post:
                content=str(content)
                sentiment_score = analyser.polarity_scores(content)['compound']
                user = UserBehavior(
                    username=str(username),
                    post_count=1,
                    high_risk_count=1 if risk_level == 'High Risk' else 0,
                    sentiment_trend=sentiment_score,
                    timestamp=timestamp
                )
                db.session.add(user)
            
            db.session.commit()
            db.session.close()
            return 

        except Exception as e:
            print("Error occured while updating the user behavior: ",e)
            return 
        

def store_high_risk_locations(df_coor):
    with app.app_context():
        for _, row in df_coor.iterrows():
            existing_entry = PostLocations.query.filter_by(username=row['username']).first()

            if not existing_entry:
                entry = PostLocations(
                    username=row['username'],
                    risk_level=row['risk_level'],
                    timestamp=row['timestamp'],
                    location=row['location'],
                    latitude=row['latitude'],
                    longitude=row['longitude']
                )
                db.session.add(entry)

        db.session.commit()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze/', methods=['GET'])
def analyze_posts():
    global df 
    df = extract_reddit_posts()
    df.dropna(inplace=True)
    df['timestamp'] = pd.to_datetime(df['timestamp'],unit='s')
    df['content'] = df['content'].apply(preprocess_text)
    df['sentiment'] = df['content'].apply(sentiment_scores)
    df['risk_level'] = df['content'].progress_apply(predict_risk_level)
    df.dropna(inplace=True)
    print("Count of risk levels",df['risk_level'].value_counts())
    
    print("Lets start analyze the users")
    for i in tqdm(range(len(df))):
        time.sleep(0.2)
        if(df.iloc[i]['post_id']!=None):
            update_user_behavior(
                post_id=df.iloc[i]['post_id'],
                username=df.iloc[i]['username'],
                content=df.iloc[i]['content'],
                risk_level=df.iloc[i]['risk_level'],
                timestamp=df.iloc[i]['timestamp']
            )
    print("Lets store the extracted posts in Database")
    store_df_in_sql(df)
    print("Lets get the coordinates of extracted location")
    df_coor=df.copy()
    df_coor=get_coordinates(df_coor)
    print("Lets store the coordinates of the location")
    store_high_risk_locations(df_coor)

    return jsonify({
        "message": "Analysis completed successfully.",
        "rows": len(df)
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=int(os.environ.get('PORT',5000)))


    