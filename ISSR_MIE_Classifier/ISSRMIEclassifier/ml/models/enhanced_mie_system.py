import pandas as pd
import numpy as np
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sentence_transformers import SentenceTransformer
import re
import logging
import json
from transformers import pipeline

class EnhancedMIESystem:
    def __init__(self, ollama_url="http://localhost:11434",, use_distilbert=False):
        self.ollama_url = ollama_url
        self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.use_distilbert = use_distilbert
        if self.use_distilbert:
            self.distilbert_sentiment = pipeline("sentiment-analysis")
        
        # Your existing death keywords
        self.death_keywords = {
            "killed", "dead", "fatalities", "deaths", "massacre", "bombing",
            "casualties", "wounded", "injured", "victims", "perished"
        }
        
        # Enhanced MIE keywords from coding instructions
        self.mie_keywords = {
            'threats': ['threat', 'warn', 'declare war', 'blockade'],
            'military': ['attack', 'clash', 'bombing', 'shelling'],
            'force_display': ['show of force', 'mobilization', 'alert'],
            'border': ['border violation', 'cross border', 'territory'],
            'official': ['military', 'army', 'navy', 'air force', 'government']
        }
    
    def check_ollama(self):
        try:
            response = requests.get(f"{self.ollama_url}/api/tags")
            return response.status_code == 200
        except:
            return False
    
    def query_ollama(self, prompt):
        logging.basicConfig(filename='ollama_debug.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
        try:
            logging.debug(f"Sending prompt to MICclass:\n{prompt}")
            payload = {
                "model": "MICclass",
                "prompt": prompt,
                "stream": False
            }
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=60)
            logging.debug(f"Ollama HTTP status: {response.status_code}")
            logging.debug(f"Ollama raw response: {response.text}")
            if response.status_code == 200:
                result = response.json()
                logging.debug(f"Ollama parsed response: {result}")
                return result.get('response', '').strip()
            else:
                logging.error(f"Ollama error: {response.status_code} {response.text}")
                return None
        except Exception as e:
            logging.error(f"Ollama exception: {e}")
            return None
    
    def extract_entities(self, text):
        """Your existing entity extraction"""
        countries = []
        fatalities = []
        
        # Country patterns
        country_patterns = [
            r'\b(?:in|from|to|of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:military|army|forces)\b'
        ]
        
        for pattern in country_patterns:
            matches = re.findall(pattern, text)
            countries.extend(matches)
        
        # Fatality patterns
        fatality_patterns = [
            r'(\d+)\s*(?:people|soldiers|civilians)\s*(?:killed|dead)',
            r'(?:killed|dead)\s*(\d+)\s*(?:people|soldiers|civilians)',
            r'(\d+)\s*(?:casualties|fatalities)'
        ]
        
        for pattern in fatality_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            fatalities.extend([int(match) for match in matches])
        
        return {
            'countries': list(set(countries)),
            'fatalities': fatalities,
            'total_fatalities': sum(fatalities) if fatalities else 0
        }
    
    def analyze_sentiment_and_keywords(self, text):
        sentiment = self.sentiment_analyzer.polarity_scores(text)
        if self.use_distilbert:
            db_result = self.distilbert_sentiment(text[:512])[0]
            distilbert_score = db_result['score'] if db_result['label'] == 'POSITIVE' else -db_result['score']
        else:
            distilbert_score = None
        
        text_lower = text.lower()
        death_count = sum(1 for word in self.death_keywords if word in text_lower)
        
        mie_count = 0
        for category, keywords in self.mie_keywords.items():
            mie_count += sum(1 for keyword in keywords if keyword in text_lower)
        
        return {
            'sentiment': sentiment['compound'],
            'death_words': death_count,
            'mie_words': mie_count,
            'is_negative': sentiment['compound'] < -0.3,
            'has_death': death_count >= 1,
            'has_mie': mie_count >= 2,
            'distilbert_sentiment': distilbert_score 
        }
    
    def create_rag_embeddings(self, articles_df):
        """Create RAG embeddings"""
        print("Creating RAG embeddings...")
        articles_df['combined_text'] = (
            articles_df['Title'].fillna('') + ' ' + 
            articles_df['Subject '].fillna('') + ' ' + 
            articles_df['Text'].fillna('')
        )
        
        texts = articles_df['combined_text'].tolist()
        self.embeddings = self.sentence_model.encode(texts)
        self.articles_data = articles_df
        print(f"Created embeddings for {len(texts)} articles")
    
    def retrieve_similar(self, query_text, top_k=3):
        """Retrieve similar articles"""
        if not hasattr(self, 'embeddings'):
            return []
        
        query_embedding = self.sentence_model.encode([query_text])
        similarities = np.dot(self.embeddings, query_embedding.T).flatten()
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        similar = []
        for idx in top_indices:
            article = self.articles_data.iloc[idx]
            similar.append({
                'title': article['Title'],
                'text': article['Text'][:200] + "...",
                'label': article['label'],
                'similarity': similarities[idx]
            })
        return similar
    
    def create_enhanced_prompt(self, title, subject, text, similar_articles):
        """Create enhanced prompt with RAG examples and enforce MICclass format"""
        
        # Prompt directing STRICT JSON output as defined in the system message
        prompt = f"""
Analyze the following article and return STRICT JSON only, per the system schema.

TITLE: {title}
SUBJECT: {subject}
TEXT: {text[:800]}...
"""
        return prompt
    
    def predict_mie(self, title, subject, text):
        """Enhanced MIE prediction combining all approaches"""
        
        # 1. Your existing entity extraction
        entities = self.extract_entities(f"{title} {subject} {text}")
        
        # 2. Your existing sentiment analysis
        sentiment = self.analyze_sentiment_and_keywords(f"{title} {subject} {text}")
        
        # 3. RAG retrieval
        combined_text = f"{title} {subject} {text}"
        similar_articles = self.retrieve_similar(combined_text, top_k=3)
        
        # 4. Ollama with RAG
        prompt = self.create_enhanced_prompt(title, subject, text, similar_articles)
        ollama_response = self.query_ollama(prompt)
        
        # 5. Parse response
        ollama_result = self.parse_response(ollama_response)
        
        # 6. Combine predictions
        final_decision = self.combine_approaches(sentiment, entities, ollama_result)
        
        return {
            'prediction': final_decision,
            'entities': entities,
            'sentiment': sentiment,
            'ollama': ollama_result,
            'similar_articles': similar_articles
        }
    
    def parse_response(self, response):
        if not response:
            return {'classification': 'UNKNOWN'}
        
        # Prefer JSON
        try:
            obj = json.loads(response.strip())
            coding = obj.get('coding', {}) or {}
            return {
                'classification': obj.get('classification', 'UNKNOWN'),
                'reasoning': obj.get('reasoning', ''),
                'action_type': coding.get('action', -9),
                'coding': coding,
                'codeable': obj.get('codeable', True),
                'missing_fields': obj.get('missing_fields', []),
                'notes': obj.get('notes', '')
            }
        except Exception:
            pass
        
        # Fallback legacy parsing
        classification = 'UNKNOWN'
        reasoning = ''
        action_type = ''
        
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line.lower().startswith('classification'):
                classification = 'MIE' if 'mie' in line.lower() and 'not' not in line.lower() else 'NOT_MIE'
            elif line.lower().startswith('reasoning'):
                reasoning = line.split(':', 1)[-1].strip()
            elif 'action' in line.lower():
                action_type = line.split(':', 1)[-1].strip()
        
        return {
            'classification': classification,
            'reasoning': reasoning,
            'action_type': action_type
        }
    
    def combine_approaches(self, sentiment, entities, ollama):
        """Combine all approaches for final decision"""
        
        # Your existing heuristic
        heuristic_score = 0
        if sentiment['is_negative'] and sentiment['has_mie']:
            heuristic_score = 1
        elif entities['total_fatalities'] > 0 and sentiment['has_death']:
            heuristic_score = 0.8
        
        # Ollama score
        ollama_score = 1 if ollama['classification'] == 'MIE' else 0
        
        # Combined decision
        final_score = (heuristic_score * 0.6) + (ollama_score * 0.4)
        return 1 if final_score >= 0.5 else 0
    
    def interactive_mode(self):
        """Interactive classification"""
        print("\n=== ENHANCED MIE SYSTEM ===")
        print("Your MIC work + RAG + LLM")
        
        while True:
            print("\n" + "-"*40)
            article_text = input("Enter article text (or 'quit' to exit): ").strip()
            if article_text.lower() == 'quit':
                break
            
            if not article_text:
                continue
            
            print("\n🔍 Analyzing...")
            
            # Get RAG context
            similar_articles = self.retrieve_similar(article_text, top_k=3)
            
            # Create prompt and get raw MICclass response
            prompt = self.create_enhanced_prompt("", "", article_text, similar_articles)
            ollama_response = self.query_ollama(prompt)
            
            print(f"\n📊 MICclass Response:")
            if ollama_response:
                print(ollama_response)
            else:
                print("❌ No response from MICclass model")
            
            # Also show the combined analysis
            result = self.predict_mie("", "", article_text)
            print(f"\n🔍 Combined Analysis:")
            print(f"Final Decision: {'MIE' if result['prediction'] == 1 else 'NOT_MIE'}")
            print(f"Countries: {result['entities']['countries']}")
            print(f"Sentiment: {result['sentiment']['sentiment']:.3f}")
            print(f"MIE Words: {result['sentiment']['mie_words']}")

def main():
    print("🚀 ENHANCED MIE CLASSIFICATION")
    print("Building on your MIC work + RAG + LLM")
    
    system = EnhancedMIESystem()
    
    if system.check_ollama():
        print("✅ Ollama connected!")
    else:
        print("❌ Ollama not available")
    
    # Load data
    df = pd.read_csv('final_data_true.csv')
    df['label'] = (df['Probable MIE'] == 1).astype(int)
    print(f"Loaded {len(df)} articles")
    
    # Create RAG embeddings
    system.create_rag_embeddings(df)
    
    # Start interactive mode
    system.interactive_mode()

if __name__ == "__main__":
    main() 