# AI for Mental Health: Bias-Aware Crisis Signal Detection and Confidence-Based Scoring System

> **Google Summer of Code (GSoC) 2026 Project** under **HumanAI**

An AI-powered backend pipeline for monitoring behavioral health discussions on Reddit. The system automatically collects Reddit posts, classifies mental health risk, performs sentiment analysis, extracts user locations using a hybrid NLP pipeline, generates behavioral insights, and stores structured outputs for downstream visualization and geospatial analysis.

---

## Project Overview

Mental health discussions on social media platforms provide valuable insights into behavioral health trends and potential crisis signals. Reddit, in particular, hosts large communities where users openly discuss depression, anxiety, stress, loneliness, substance abuse, and suicidal ideation.

This project aims to develop an AI-powered backend pipeline that automatically processes Reddit posts into structured behavioral health information. The pipeline integrates machine learning, natural language processing, geolocation extraction, and behavioral analytics to support future visualization and spatial hotspot detection while maintaining a scalable and cost-efficient architecture.

---

## Features

- Reddit data collection using PRAW
- Text preprocessing and keyword filtering
- Mental health risk classification using a fine-tuned DistilBERT model
- Sentiment analysis using VADER
- Hybrid geolocation extraction using spaCy, OpenAI GPT, and Nominatim
- User behavior analysis
- SQLite database for structured storage
- Data visualization and exploratory analysis
- Global heatmap generation

---

# System Architecture

 <img width="1070" height="630" alt="Screenshot 2026-07-03 223243" src="https://github.com/user-attachments/assets/2a50597b-9a35-4b4a-89b8-877205b61369" />


---

# Technologies Used

| **Category** | **Technologies Used** |
|--------------|-----------------------|
| Programming Language | Python |
| Reddit Data Collection | PRAW (Reddit API) |
| Deep Learning Framework | PyTorch |
| Risk Classification | Fine-tuned DistilBERT (Hugging Face Transformers) |
| Sentiment Analysis | VADER Sentiment |
| Named Entity Recognition | spaCy |
| Contextual Location Inference | OpenAI (via LangChain) |
| Geocoding | Nominatim, GeoPy |
| Data Processing | Pandas, NumPy |
| Database | SQLite |
| Data Visualization | Matplotlib, WordCloud, Folium |

---

# Dataset

Since no publicly available dataset directly matched the project's three-level mental health risk taxonomy (**High Risk**, **Moderate Risk**, and **Low Risk**), a custom dataset was constructed by merging, cleaning, relabeling, and standardizing two publicly available datasets.

## Dataset Sources

### 1. Sentiment Analysis for Mental Health

https://www.kaggle.com/datasets/suchintikasarkar/sentiment-analysis-for-mental-health

### 2. Suicidal Tweet Detection Dataset

https://www.kaggle.com/datasets/aunanya875/suicidal-tweet-detection-dataset

---

## Dataset Construction

The custom dataset was created through the following preprocessing pipeline:

- Combined both source datasets
- Removed missing and invalid records
- Removed duplicate samples
- Text normalization and standardization
- Unified label schema
- Mapped the original labels into three behavioral health risk categories

---

## Dataset Statistics

**Total Samples:** **47,894**

**Number of Classes:** **3**

| **Risk Level** | **Description** | **Samples** |
|----------------|-----------------|------------:|
| 🔴 High Risk | Explicit suicidal ideation, suicide planning, self-harm intent, or immediate crisis | 12,064 |
| 🟡 Moderate Risk | Depression, anxiety, emotional distress, stress, or substance abuse without explicit suicidal intent | 19,487 |
| 🟢 Low Risk | General discussions, daily life experiences, emotionally neutral, or non-crisis mental health conversations | 16,343 |

---

# Risk Classification Model

A **DistilBERT-based transformer model** was fine-tuned to classify Reddit posts into three behavioral health risk categories.

## Model Configuration

| Parameter | Value |
|------------|-------|
| Base Model | distilbert-base-uncased |
| Framework | Hugging Face Transformers |
| Deep Learning Library | PyTorch |
| Task | Multi-class Text Classification |
| Learning Rate | 2e-5 |
| Batch Size | 8 |
| Epochs | 3 |
| Optimizer | AdamW |
| Weight Decay | 0.01 |

---

## Model Performance

| Epoch | Training Loss | Validation Loss | Accuracy | Weighted F1 |
|-------:|--------------:|----------------:|----------:|------------:|
| 1 | 0.2657 | 0.4282 | 85.45% | 85.32% |
| 2 | 0.2367 | 0.5043 | **85.80%** | **85.71%** |
| 3 | 0.1542 | 0.6890 | 85.79% | 85.69% |

**Best Validation Accuracy:** **85.80%**

**Best Weighted F1 Score:** **85.71%**

---

# Geolocation Extraction

One of the major challenges in behavioral health monitoring is accurately identifying a user's location from unstructured Reddit posts.

To balance accuracy and API costs, the project employs a **hybrid location extraction pipeline**:

1. **spaCy Named Entity Recognition (NER)** identifies posts containing potential location entities.
2. **OpenAI GPT (via LangChain)** performs contextual reasoning to determine whether the extracted location refers to the user's own location.
3. **Nominatim** converts inferred locations into latitude and longitude coordinates.

This significantly reduces the number of LLM API calls while improving location inference accuracy.

---

# Repository Structure

```
ISSR_AI4MH_Gokulan_M/
│
├── assets/                        # Project assets
├── pictures/                      # Generated visualizations
├── pipeline/                      # Backend processing modules
├── static/                        # Static files
├── templates/                     # HTML templates
│
├── AnalysingPosts.ipynb           # Data analysis and visualization
├── RiskClassificationModel.ipynb  # DistilBERT model training
├── main.py                        # Main application
├── requirements.txt
└── README.md
```

---
 
# Visualizations

The backend generates multiple visualizations, including:

- Risk Level Distribution
- Sentiment Distribution
- Word Cloud
- Country-wise Distribution
- State-wise Distribution
- City-wise Distribution
- Global Heatmap
- User Activity Distribution
- Engagement Analysis
- Temporal Trends

---

# Current Progress

| Module | Status |
|---------|--------|
| Reddit Data Collection | ✅ Completed |
| Data Preprocessing | ✅ Completed |
| Risk Classification | ✅ Completed |
| Sentiment Analysis | ✅ Completed |
| Geolocation Extraction | ✅ Completed |
| User Behavior Analysis | ✅ Completed |
| SQLite Database | ✅ Completed |
| Data Visualization | ✅ Completed |
| Dashboard Development | 🚧 In Progress |
| Confidence-Based Scoring | ⏳ Planned |
| Bias-Aware Analysis | ⏳ Planned |

---

# Future Work

The remaining phases of the project include:

- Interactive dashboard development
- Geospatial hotspot detection
- Confidence-based scoring framework
- Bias-aware behavioral health analysis
- County-level demographic data integration
- Performance optimization
- End-to-end deployment

---

# Acknowledgements

This project is being developed as part of **Google Summer of Code (GSoC) 2026** under **HumanAI**.

### Mentors

- David White
- Hailey Richardson
- Anna Thrash

I also acknowledge the creators of the publicly available datasets and the open-source communities behind Hugging Face, PyTorch, spaCy, PRAW, VADER, GeoPy, and Nominatim, whose tools and resources made this project possible.
---

# Disclaimer

This project is intended **solely for research, educational, and demonstration purposes** as part of **Google Summer of Code (GSoC) 2026** under HumanAI.

The mental health risk classification model is **not a medical device** and **must not be used for real-world clinical decision-making, crisis intervention, diagnosis, or treatment**. The predictions generated by the model are based on machine learning techniques and may produce incorrect or incomplete results.

The model should **not** be deployed in production environments where its outputs could directly impact individuals without appropriate clinical oversight and rigorous validation.

The dataset used for training was constructed by merging publicly available datasets and is intended for research purposes only. As such, the model may inherit biases and limitations present in the source data.

Users of this repository are responsible for ensuring that any use of the code, models, or datasets complies with applicable ethical guidelines, privacy regulations, and institutional review policies.

---
 
# License

This project is intended for **research and educational purposes**. Please ensure ethical and responsible use when working with mental health-related data.
