# Enhanced MIE Classifier - GSOC Project

A comprehensive system for classifying Military and International Events (MIE) articles using machine learning, RAG, and sentiment analysis.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip
- Git

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd GSOC
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Download Required NLTK Data**
```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('averaged_perceptron_tagger_eng'); nltk.download('maxent_ne_chunker_tab'); nltk.download('words')"
```

4. **Setup Ollama (Optional but Recommended)**
   - Visit [ollama.ai](https://ollama.ai/) and download for your OS
   - Start Ollama service:
   ```bash
   # On Windows (PowerShell):
   ollama serve
   
   # On macOS/Linux:
   ollama serve &
   ```
   - Pull required model:
   ```bash
   ollama pull gemma3:latest
   ```
   - Setup MIE Expert model:
   ```bash
   # On Windows (PowerShell):
   ./setup_ollama.sh
   
   # On macOS/Linux:
   chmod +x setup_ollama.sh
   ./setup_ollama.sh
   ```

### Running the Enhanced MIE Classifier

**Option 1: Interactive Mode (Recommended)**
```bash
python main.py
```
This will start an interactive session where you can:
- Enter article title, subject, and text to classify
- Get detailed analysis with confidence scores
- See ML prediction, Ollama analysis, RAG similar articles
- View sentiment analysis and entity extraction

**Option 2: Programmatic Usage**
```python
from ml.models.enhanced_mie_classifier import EnhancedMIEClassifier

# Initialize classifier
classifier = EnhancedMIEClassifier(model_name="mie-expert")

# Load and train on data
df = classifier.load_and_prepare_data('data/raw/final_data_true.csv')
X = df['Title'].fillna('') + ' ' + df['Subject '].fillna('') + ' ' + df['Text'].fillna('')
y = df['label']
classifier.train_enhanced_model(X, y)

# Classify an article
result = classifier.predict_enhanced_mie(
    title="U.S. military conducts airstrikes in Syria",
    subject="Military action",
    text="The United States military launched targeted airstrikes..."
)
print(result)
```

## 📁 Project Structure

```
GSOC/
├── main.py                          # Main entry point
├── requirements.txt                 # Python dependencies
├── setup_ollama.sh                 # Ollama setup script
├── data/
│   └── raw/
│       ├── final_data_true.csv     # Training dataset (248 MIE + 248 non-MIE)
│       ├── MIE_Coding_Instructions.txt  # Coding guidelines
│       ├── mie_articles_only.csv   # MIE-only articles
│       └── non_mie_248.csv         # Non-MIE articles
├── ml/
│   ├── models/
│   │   ├── enhanced_mie_classifier.py  # Core classifier
│   │   ├── enhanced_mie_system.py      # Enhanced system
│   │   └── hybrid_classifier.py        # Hybrid approach
│   ├── training/
│   │   └── train.py                    # Training script
│   └── evaluation/
│       ├── evaluate.py                 # Evaluation script
│       └── test_mie_expert.py          # Expert testing
├── nlp/
│   ├── preprocessing/
│   │   └── text_processor.py           # Text preprocessing
│   ├── analysis/
│   │   └── sentiment_analyzer.py       # Sentiment analysis
│   └── extraction/
│       └── entity_extractor.py         # Entity extraction
├── rag/
│   ├── context/
│   │   └── context_builder.py          # Context building
│   ├── retrieval/
│   │   └── retriever.py                # Document retrieval
│   └── vectorstore/
│       └── embedding_store.py          # Vector embeddings
└── ollama/
    ├── integration/
    │   └── mie_classifier.py           # LLM integration
    ├── models/
    │   ├── Modelfile                   # Model definition
    │   └── README.md                   # Model documentation
    └── prompts/
        └── README.md                   # Prompt documentation
```
```

## 🔧 System Components

The Enhanced MIE Classifier combines:

1. **Machine Learning**: TF-IDF + Naive Bayes/Random Forest
2. **RAG (Retrieval Augmented Generation)**: Similar article retrieval
3. **Ollama LLM**: Custom MIE Expert model for classification
4. **Sentiment Analysis**: VADER sentiment scoring
5. **Entity Extraction**: Country names, fatality counts
6. **MIC Heuristics**: Death word analysis and MIE keywords

## 📊 Data Format

Your CSV files should have these columns:
- `Title`: Article headline
- `Subject`: Article subject/category
- `Text`: Article content
- `label`: MIE classification (1=MIE, 0=non-MIE)

Example:
```csv
Title,Subject,Text,label
"US Military Strike in Syria","Military","The US launched airstrikes...",1
"Local Weather Report","Weather","Today's weather will be sunny...",0
```

## 🎯 Features

### Enhanced MIE Classifier Capabilities:
1. **Multi-Modal Classification**: Combines ML, RAG, and LLM approaches
2. **Sentiment Analysis**: Analyzes emotional content and MIE keywords
3. **Entity Extraction**: Identifies countries, organizations, fatalities
4. **RAG System**: Retrieves similar articles for context
5. **Confidence Scoring**: Provides reliability metrics
6. **Interactive Mode**: Real-time classification with detailed analysis

### Classification Criteria:
- **Military keywords**: attack, invasion, war, troops, bombing, etc.
- **International events**: diplomatic incidents, conflicts, border violations
- **Geographic indicators**: country names, regions, territories
- **Temporal patterns**: recent events, ongoing conflicts
- **Entity relationships**: state actors, organizations, casualties

## 🐛 Troubleshooting

### Common Issues:

1. **Ollama Connection Issues**
   ```bash
   # Check if Ollama is running
   curl http://localhost:11434/api/tags
   
   # Restart Ollama service
   ollama serve
   ```

2. **Missing Dependencies**
   ```bash
   # Reinstall requirements
   pip install -r requirements.txt --force-reinstall
   ```

3. **NLTK Data Issues**
   ```bash
   python -c "import nltk; nltk.download('all')"
   ```

4. **Data file not found**
   - Ensure `data/raw/final_data_true.csv` exists
   - Check file permissions

### Performance Tips:
- Use GPU if available for faster LLM inference
- The system works with the provided `final_data_true.csv` (2.5MB)
- For larger datasets, consider processing in batches

## 📈 Training Data

The system comes with `final_data_true.csv` containing:
- **248 MIE articles** (label=1)
- **248 non-MIE articles** (label=0)
- **Total**: 496 articles for training
- **Size**: ~2.5MB

## 🎉 Success Indicators

You'll know everything is working when:

1. ✅ `python main.py` starts without errors
2. ✅ Shows "496 articles for training"
3. ✅ Interactive mode accepts article input
4. ✅ Classification results show confidence scores
5. ✅ Ollama integration works (if enabled)

## 📝 Example Usage

```python
# Interactive classification
python main.py

# Programmatic usage
from ml.models.enhanced_mie_classifier import EnhancedMIEClassifier

classifier = EnhancedMIEClassifier(model_name="mie-expert")
df = classifier.load_and_prepare_data('data/raw/final_data_true.csv')
X = df['Title'].fillna('') + ' ' + df['Subject '].fillna('') + ' ' + df['Text'].fillna('')
y = df['label']
classifier.train_enhanced_model(X, y)

# Classify an article
result = classifier.predict_enhanced_mie(
    title="U.S. military conducts airstrikes in Syria",
    subject="Military action",
    text="The United States military launched targeted airstrikes..."
)
print(f"Classification: {'MIE' if result['final_prediction'] == 1 else 'Non-MIE'}")
print(f"Confidence: {result['confidence']:.2f}")
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is part of Google Summer of Code 2025.

---

**Ready to classify MIE articles? Run `python main.py` and start analyzing! 🚀** 