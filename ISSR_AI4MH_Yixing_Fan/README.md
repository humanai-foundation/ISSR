# GSoC2025-AI4MH

**AI-powered Behavioral Analysis for Mental Health Crisis Detection**  
GSoC 2025 @ HumanAI
![AI4MH Project Logo](LOGO-1.png)
---

## 🧠 Overview

This project develops an AI-powered system for early detection and monitoring of mental health crises—including suicide risk, substance use, and emotional distress—using social media data.  

We build a modular NLP pipeline that:  
- Detects high-risk language and suicidal ideation.  
- Classifies sentiment and risk levels.  
- Provides interpretable outputs (word banks, word clouds, metrics).  
- Evaluates model generalization on external datasets (e.g., Kaggle).  

> **Note:** Geospatial trend analysis was considered but not included in this release due to privacy concerns.  

---

## 👥 Team

- **Mentor**: [Dr. David White](mailto:dmwhite@ua.edu)
- **Primary Developer**: [Yixing (Spark) Fan](https://www.linkedin.com/in/yixing-spark-fan/)
- **Contributor**: [Vishnu Sankhyan](https://github.com/Vishnusankhyan13)

---

## 📌 Key Features

- Unified supervised dataset combining Reddit + public datasets.  
- Data cleaning scripts for deduplication, label unification, and preprocessing.  
- Fine-tuned BERT classifier for suicide risk detection.  
- Sentiment and risk-level classification with VADER + keyword heuristics.  
- Google Trends integration for crisis-related keyword tracking.  
- Word bank and word cloud visualization tools.  
- Evaluation pipeline with confusion matrix, ROC/PR curves, and threshold analysis.  

---

## 🚧 Current Status

✅ Data collection & cleaning completed  
✅ Unified dataset prepared ([`unified_supervised_v2.csv`](dataset/unified_supervised_v2.csv))  
✅ BERT fine-tuning implemented ([`train_bert_from_unified.py`](pipeline/train_bert_from_unified.py))  
✅ Model evaluation on external Kaggle dataset  
✅ Word bank & sentiment risk outputs  
✅ Midterm and final reports ([`midterm_report.ipynb`](reports/midterm_report.ipynb), [`final_report.ipynb`](reports/final_report.ipynb))  

🔜 Future work: explainability tools, cross-platform expansion, geospatial trends with privacy safeguards  

---

## 📂 Repo Structure

```bash
dataset/                 # Input datasets
  ├─ kaggle_clean.csv
  ├─ Suicidal Ideation Detection Reddit Dataset-Version 2.csv
  ├─ Suicide_Detection.csv
  └─ Suicide_Ideation_Dataset(Twitter-based).csv

output/                  # Generated outputs
  ├─ mental_health_wordcloud.png
  ├─ sentiment_risk_classified.csv
  ├─ word_bank.csv
  └─ ...

pipeline/                # Core pipeline scripts
  ├─ bert.py
  ├─ train_bert_from_unified.py
  ├─ eval_csv_iterator.py
  ├─ eval_large_csv.py
  ├─ clean_kaggle.py
  ├─ merge_kaggle.py
  ├─ split_supervised.py
  ├─ fetch_reddit.py
  ├─ generate_word_bank.py
  ├─ generate_wordcloud.py
  ├─ google_trend_demo.py
  └─ test_model.py

results/                 # Model checkpoints and evaluation outputs

reports/                 # Notebooks and documentation
  ├─ midterm_report.ipynb
  └─ final_report.ipynb

requirements.txt         # Python dependencies
README.md                # Project description
```
---

## 📖 License
This project will use the MIT License unless otherwise specified.

---

## 🙌 Acknowledgments
This project was carried out under the supervision of **David White**, with organizational support from **HumanAI** and the **Institute for Social Science Research, The University of Alabama**, and made possible through the **Google Summer of Code 2025**.


---
## 📚 Dataset Attribution

This project uses the following publicly available dataset:

**1. Suicidal Ideation Detection Reddit Dataset**  
Mafi, Md Mafiul Hasan Matin; Alam, Md. Sabbir (2023),  
“Suicidal Ideation Detection Reddit Dataset”,  
Mendeley Data, V2, https://doi.org/10.17632/z8s6w86tr3.2  
Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

The dataset is used for research purposes only and is not redistributed for commercial use. All rights belong to the original authors.

**2. Suicide and Depression Detection**  
Kaggle Suicide and Depression Detection,
https://www.kaggle.com/datasets/nikhileswarkomati/suicide-watch/data