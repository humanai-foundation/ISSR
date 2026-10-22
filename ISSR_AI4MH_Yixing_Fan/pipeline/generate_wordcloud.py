import pandas as pd
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
import os

# ===== Path settings =====
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # Project root directory
WORD_BANK_PATH = os.path.join(BASE_DIR, "output", "word_bank.csv")
OUTPUT_IMG_PATH = os.path.join(BASE_DIR, "output", "mental_health_wordcloud.png")

# ===== Read word_bank.csv =====
df = pd.read_csv(WORD_BANK_PATH)

# ===== Stopword settings =====
stopwords = set(STOPWORDS)
custom_stopwords = {"m", "don", "im", "t", "s", "ll", "ve", "re"}  # Customized meaningless words
stopwords.update(custom_stopwords)

# ===== Build word frequency dictionary, filter out stopwords and words with length < 3 =====
word_freq = {
    row['word']: row['frequency']
    for _, row in df.iterrows()
    if row['word'].lower() not in stopwords and len(row['word']) >= 3
}

# ===== Generate word cloud =====
wc = WordCloud(
    width=1000,
    height=600,
    background_color="white",
    stopwords=stopwords,
    colormap="viridis"  # Color mapping, can be changed to 'plasma', 'inferno' etc.
)
wc.generate_from_frequencies(word_freq)

# ===== Save word cloud =====
wc.to_file(OUTPUT_IMG_PATH)
print(f"Word cloud saved to {OUTPUT_IMG_PATH}")

# ===== Display word cloud (if GUI/interactive mode enabled) =====
if os.environ.get("SHOW_PLOT", "").lower() in ("1", "true"):
    plt.imshow(wc, interpolation="bilinear")
    plt.axis("off")
    plt.show()
plt.close()
