import pandas as pd
from nltk.corpus import stopwords
import nltk
import spacy
from geopy.geocoders import Nominatim

nlp=spacy.load('en_core_web_sm')
nltk.download('stopwords')
STOPWORDS= set(stopwords.words('english'))
geolocator= Nominatim(user_agent='crisis_detector')
 
def extract_location(text):
    if isinstance(text,str):
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ == 'GPE' or ent.label_ == 'LOC':
                return ent.text

    return None        
    
def geocode_location(place):
    try:
        
        location = geolocator.geocode(place, addressdetails=True,language='en',timeout=10)
        if location:
            latitude = location.latitude
            longitude = location.longitude
            address = location.raw.get('address',{})
            city=address.get('city') or address.get('town') or address.get('village')
            state=address.get('state')
            country=address.get('country')
            location_mapped= city or state or country

            return pd.Series({'latitude':latitude,'longitude':longitude,'location':location_mapped})
        
        return pd.Series({'latitude':None,'longitude':None,'location':None})
    except Exception as e:
        print("Error occured while extracting coordinates :",e)
        return pd.Series({'latitude':None,'longitude':None,'location':None})
    
def get_coordinates(df_coor):

    df_coor['location'] = df_coor['content'].progress_apply(lambda x: extract_location(str(x)))
    df_coor.dropna(inplace=True)
    df_coor['location'] = df_coor['location'].str.title()
    print("Dataframe of extracted Locations",df_coor.info())
    df_coor[['latitude','longitude','location']] = df_coor['location'].progress_apply(lambda x:geocode_location(x))
     
    df_coor.dropna(inplace=True)

    if df_coor.empty:
        print("No Valid Coordinates found.")
        return

    print("Coordinates Completed.")   
    print("Dataframe after extracting Coordinates",df_coor.info())
     
    return df_coor