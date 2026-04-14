"""
Text Preprocessing for MIE Classification
"""

import re
from typing import List, Dict, Any
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer, PorterStemmer

try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('wordnet')

class TextProcessor:
    """Text preprocessing for MIE articles"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.stop_words = set(stopwords.words('english'))
        self.lemmatizer = WordNetLemmatizer()
        self.stemmer = PorterStemmer()
        self.max_length = config["nlp"]["max_text_length"]
        
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
            
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters but keep important punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', ' ', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def remove_stopwords(self, text: str) -> str:
        """Remove stopwords if configured"""
        if not self.config["nlp"]["remove_stopwords"]:
            return text
            
        words = word_tokenize(text)
        filtered_words = [word for word in words if word.lower() not in self.stop_words]
        return ' '.join(filtered_words)
    
    def lemmatize_text(self, text: str) -> str:
        """Lemmatize text if configured"""
        if not self.config["nlp"]["lemmatize"]:
            return text
            
        words = word_tokenize(text)
        lemmatized_words = [self.lemmatizer.lemmatize(word) for word in words]
        return ' '.join(lemmatized_words)
    
    def stem_text(self, text: str) -> str:
        """Stem text using Porter Stemmer.

        Stemming is a faster, rule-based approach that strips word suffixes
        (e.g. 'running' -> 'run', 'studies' -> 'studi'). It is intentionally
        kept separate from lemmatization: applying both would let the stemmer
        undo the linguistically precise output of the lemmatizer, so the two
        methods should be treated as alternative normalisation strategies rather
        than sequential steps.
        """
        words = word_tokenize(text)
        stemmed_words = [self.stemmer.stem(word) for word in words]
        return ' '.join(stemmed_words)

    def truncate_text(self, text: str) -> str:
        """Truncate text to maximum length"""
        if len(text) <= self.max_length:
            return text
            
        # Try to truncate at sentence boundary
        sentences = sent_tokenize(text)
        truncated = ""
        
        for sentence in sentences:
            if len(truncated + sentence) <= self.max_length:
                truncated += sentence + " "
            else:
                break
                
        return truncated.strip()
    
    def preprocess(self, title: str, subject: str, text: str, stemming: bool = False) -> str:
        """Complete preprocessing pipeline.

        Args:
            title:    Article title.
            subject:  Article subject / topic line.
            text:     Article body.
            stemming: When False (default) the pipeline applies cleaning →
                      stopword removal → lemmatization → truncation.
                      When True, lemmatization is replaced by Porter Stemmer
                      (cleaning → stopword removal → stemming → truncation).
                      Combining both normalisation strategies is avoided because
                      the stemmer would aggressively re-stem the precise output
                      of the lemmatizer, degrading token quality rather than
                      improving it.
        """
        # Combine all text fields
        combined_text = f"{title} {subject} {text}"

        # Shared early steps
        cleaned = self.clean_text(combined_text)
        no_stopwords = self.remove_stopwords(cleaned)

        if stemming:
            # Stemming-only path: faster, more aggressive normalisation
            normalised = self.stem_text(no_stopwords)
        else:
            # Lemmatization-only path: linguistically precise normalisation
            normalised = self.lemmatize_text(no_stopwords)

        return self.truncate_text(normalised)
    
    def chunk_text(self, text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
        """Split text into chunks for RAG"""
        if chunk_size is None:
            chunk_size = self.config["rag"]["chunk_size"]
        if overlap is None:
            overlap = self.config["rag"]["chunk_overlap"]
            
        sentences = sent_tokenize(text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk + sentence) <= chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
        
        # Add the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract key entities for MIE classification"""
        entities = {
            "countries": [],
            "military_terms": [],
            "dates": [],
            "locations": []
        }
        
        # Extract countries (basic pattern)
        country_pattern = r'\b(United States|USA|Russia|China|Iran|Iraq|Syria|Ukraine|Israel|Palestine|North Korea|South Korea|Japan|India|Pakistan|Afghanistan|Yemen|Somalia|Libya|Egypt|Turkey|Saudi Arabia|Qatar|UAE|Kuwait|Bahrain|Oman|Jordan|Lebanon|Mali|Niger|Chad|Sudan|Ethiopia|Eritrea|Djibouti|Kenya|Tanzania|Uganda|Rwanda|Burundi|Congo|Central African Republic|Cameroon|Nigeria|Ghana|Ivory Coast|Liberia|Sierra Leone|Guinea|Senegal|Mauritania|Morocco|Algeria|Tunisia|Libya|Egypt|Sudan|South Sudan|Ethiopia|Eritrea|Djibouti|Somalia|Kenya|Tanzania|Uganda|Rwanda|Burundi|Congo|Central African Republic|Cameroon|Nigeria|Ghana|Ivory Coast|Liberia|Sierra Leone|Guinea|Senegal|Mauritania|Morocco|Algeria|Tunisia)\b'
        entities["countries"] = re.findall(country_pattern, text, re.IGNORECASE)
        
        # Extract military terms
        military_pattern = r'\b(army|navy|air force|military|troops|soldiers|bombers|fighters|missiles|tanks|artillery|special forces|marines|aircraft|warships|submarines|drones|helicopters|battalions|brigades|divisions|corps|commandos|snipers|saboteurs|insurgents|militants|terrorists|rebels|guerrillas|paramilitary|militia|defense|offense|attack|defend|invade|occupy|retreat|advance|surrender|ceasefire|armistice|truce|peace|war|battle|conflict|clash|skirmish|engagement|operation|mission|deployment|mobilization|alert|threat|ultimatum|warning|protest|sanctions|embargo|blockade|siege|bombardment|shelling|airstrike|ground assault|amphibious|airborne|mechanized|armored|infantry|artillery|air defense|missile defense|electronic warfare|cyber warfare|information warfare|psychological warfare|economic warfare|diplomatic|negotiation|mediation|arbitration|conciliation|good offices|peacekeeping|peacemaking|peacebuilding|conflict resolution|conflict prevention|early warning|crisis management|conflict management|conflict transformation|conflict settlement|conflict termination|conflict escalation|conflict de-escalation|conflict containment|conflict limitation|conflict regulation|conflict control|conflict suppression|conflict elimination|conflict eradication|conflict annihilation|conflict destruction|conflict obliteration|conflict extinction|conflict extermination|conflict liquidation|conflict elimination|conflict removal|conflict expulsion|conflict ejection|conflict eviction|conflict ouster|conflict deposition|conflict dethronement|conflict overthrow|conflict coup|conflict revolution|conflict insurrection|conflict rebellion|conflict uprising|conflict revolt|conflict mutiny|conflict sedition|conflict treason|conflict espionage|conflict sabotage|conflict subversion|conflict infiltration|conflict penetration|conflict incursion|conflict intrusion|conflict violation|conflict breach|conflict infringement|conflict transgression|conflict trespass|conflict encroachment|conflict invasion|conflict occupation|conflict annexation|conflict conquest|conflict subjugation|conflict domination|conflict control|conflict influence|conflict pressure|conflict coercion|conflict intimidation|conflict blackmail|conflict extortion|conflict ransom|conflict tribute|conflict levy|conflict tax|conflict tariff|conflict duty|conflict customs|conflict excise|conflict toll|conflict fee|conflict charge|conflict cost|conflict price|conflict value|conflict worth|conflict merit|conflict quality|conflict grade|conflict rank|conflict status|conflict position|conflict standing|conflict reputation|conflict prestige|conflict honor|conflict dignity|conflict respect|conflict esteem|conflict regard|conflict consideration|conflict attention|conflict notice|conflict recognition|conflict acknowledgment|conflict admission|conflict confession|conflict declaration|conflict statement|conflict announcement|conflict proclamation|conflict publication|conflict disclosure|conflict revelation|conflict exposure|conflict discovery|conflict detection|conflict identification|conflict determination|conflict establishment|conflict confirmation|conflict verification|conflict validation|conflict authentication|conflict certification|conflict accreditation|conflict authorization|conflict approval|conflict consent|conflict permission|conflict license|conflict permit|conflict warrant|conflict mandate|conflict commission|conflict delegation|conflict assignment|conflict appointment|conflict nomination|conflict election|conflict selection|conflict choice|conflict preference|conflict option|conflict alternative|conflict substitute|conflict replacement|conflict successor|conflict heir|conflict beneficiary|conflict recipient|conflict addressee|conflict target|conflict objective|conflict goal|conflict aim|conflict purpose|conflict intention|conflict motive|conflict reason|conflict cause|conflict source|conflict origin|conflict root|conflict basis|conflict foundation|conflict ground|conflict justification|conflict rationale|conflict explanation|conflict account|conflict description|conflict narrative|conflict story|conflict tale|conflict report|conflict record|conflict document|conflict file|conflict dossier|conflict portfolio|conflict collection|conflict compilation|conflict anthology|conflict selection|conflict anthology|conflict compilation|conflict collection|conflict portfolio|conflict dossier|conflict file|conflict document|conflict record|conflict report|conflict story|conflict tale|conflict narrative|conflict description|conflict account|conflict explanation|conflict rationale|conflict justification|conflict ground|conflict foundation|conflict basis|conflict root|conflict origin|conflict source|conflict cause|conflict reason|conflict motive|conflict intention|conflict purpose|conflict aim|conflict goal|conflict objective|conflict target|conflict addressee|conflict recipient|conflict beneficiary|conflict heir|conflict successor|conflict replacement|conflict substitute|conflict alternative|conflict option|conflict preference|conflict choice|conflict selection|conflict election|conflict nomination|conflict appointment|conflict assignment|conflict delegation|conflict commission|conflict mandate|conflict warrant|conflict permit|conflict license|conflict permission|conflict consent|conflict approval|conflict authorization|conflict accreditation|conflict certification|conflict authentication|conflict validation|conflict verification|conflict confirmation|conflict establishment|conflict determination|conflict identification|conflict detection|conflict discovery|conflict exposure|conflict revelation|conflict disclosure|conflict publication|conflict proclamation|conflict announcement|conflict statement|conflict declaration|conflict confession|conflict admission|conflict acknowledgment|conflict recognition|conflict notice|conflict attention|conflict consideration|conflict regard|conflict esteem|conflict respect|conflict dignity|conflict honor|conflict prestige|conflict reputation|conflict standing|conflict position|conflict status|conflict rank|conflict grade|conflict quality|conflict worth|conflict value|conflict price|conflict cost|conflict charge|conflict fee|conflict toll|conflict excise|conflict customs|conflict duty|conflict tariff|conflict tax|conflict levy|conflict tribute|conflict ransom|conflict extortion|conflict blackmail|conflict intimidation|conflict coercion|conflict pressure|conflict influence|conflict control|conflict domination|conflict subjugation|conflict conquest|conflict annexation|conflict occupation|conflict invasion|conflict encroachment|conflict trespass|conflict transgression|conflict infringement|conflict breach|conflict violation|conflict intrusion|conflict incursion|conflict penetration|conflict infiltration|conflict subversion|conflict sabotage|conflict espionage|conflict treason|conflict sedition|conflict mutiny|conflict revolt|conflict uprising|conflict rebellion|conflict insurrection|conflict revolution|conflict coup|conflict overthrow|conflict dethronement|conflict deposition|conflict ouster|conflict eviction|conflict ejection|conflict expulsion|conflict removal|conflict elimination|conflict liquidation|conflict extermination|conflict extinction|conflict obliteration|conflict destruction|conflict annihilation|conflict eradication|conflict elimination|conflict control|conflict regulation|conflict limitation|conflict containment|conflict de-escalation|conflict escalation|conflict termination|conflict settlement|conflict transformation|conflict management|conflict prevention|conflict early warning|conflict crisis management|conflict peacebuilding|conflict peacemaking|conflict peacekeeping|conflict good offices|conflict conciliation|conflict arbitration|conflict mediation|conflict negotiation|conflict diplomatic|conflict economic warfare|conflict psychological warfare|conflict information warfare|conflict cyber warfare|conflict electronic warfare|conflict missile defense|conflict air defense|conflict artillery|conflict infantry|conflict armored|conflict mechanized|conflict airborne|conflict amphibious|conflict ground assault|conflict airstrike|conflict shelling|conflict bombardment|conflict siege|conflict blockade|conflict embargo|conflict sanctions|conflict protest|conflict warning|conflict ultimatum|conflict threat|conflict alert|conflict mobilization|conflict deployment|conflict mission|conflict operation|conflict engagement|conflict skirmish|conflict clash|conflict battle|conflict war|conflict peace|conflict truce|conflict armistice|conflict ceasefire|conflict surrender|conflict advance|conflict retreat|conflict occupy|conflict invade|conflict defend|conflict attack|conflict offense|conflict defense|conflict militia|conflict paramilitary|conflict guerrillas|conflict rebels|conflict terrorists|conflict militants|conflict insurgents|conflict snipers|conflict commandos|conflict corps|conflict divisions|conflict brigades|conflict battalions|conflict helicopters|conflict drones|conflict submarines|conflict warships|conflict aircraft|conflict marines|conflict special forces|conflict artillery|conflict tanks|conflict missiles|conflict fighters|conflict bombers|conflict soldiers|conflict troops|conflict military|conflict air force|conflict navy|conflict army)\b'
        entities["military_terms"] = re.findall(military_pattern, text, re.IGNORECASE)
        
        # Extract dates (basic pattern)
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b|\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
        entities["dates"] = re.findall(date_pattern, text, re.IGNORECASE)
        
        return entities 