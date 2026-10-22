import pandas as pd
from collections import Counter
import re
import os
import contractions
from wordcloud import STOPWORDS

# ===== Path settings =====
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
input_path = os.path.join(BASE_DIR, "dataset", "Suicidal Ideation Detection Reddit Dataset-Version 2.csv")
output_path = os.path.join(BASE_DIR, "output", "word_bank.csv")

# ===== Read data =====
df = pd.read_csv(input_path)

# ===== Get last column as label column =====
label_col = df.columns[-1]
df[label_col] = df[label_col].astype(str).str.lower()

# ===== Only keep suicidal label =====
suicidal_df = df[df[label_col] == "suicidal"]

# ===== Text column =====
text_col = df.columns[0]
texts = suicidal_df[text_col].dropna().tolist()

# ===== Stopwords (default + customized) =====
stopwords = set(STOPWORDS)
custom_stopwords = {"m", "don", "im", "t", "s", "ll", "ve", "re"}  # 常见缩写残留
stopwords.update(custom_stopwords)

# ===== Process text, expand contractions + tokenize =====
words = []
for text in texts:
    expanded_text = contractions.fix(text.lower())  # Expand contractions
    tokens = re.findall(r'\b\w+\b', expanded_text)  # Extract words
    for token in tokens:
        if len(token) >= 3 and token not in stopwords:  # Filter stopwords & short words
            words.append(token)

# ===== Count word frequency, take top 200 =====
counter = Counter(words)
most_common = counter.most_common(200)

# ===== Save CSV =====
pd.DataFrame(most_common, columns=["word", "frequency"]).to_csv(output_path, index=False)
print(f"Word bank saved to {output_path}")
