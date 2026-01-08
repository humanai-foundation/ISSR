
# Communication Analysis Tool for Human-AI Interaction Driving Simulator Experiments

![banner](assets/image.png)

This repository contains a web application for TRIP-LAB that analyzes communication data in group simulation settings by processing video files to understand group dynamics through advanced data analytics and AI modeling.

## Overview

This project analyzes communication text to extract insights such as sentiment, emotion, and linguistic patterns using NLP techniques.

The project consists of two main components:
1. A video/audio processing pipeline that extracts audio, performs speaker segmentation, transcribes speech, and analyzes sentiment and tone.
2. A Gradio-based visualization interface that displays analysis results through interactive plots and CSV outputs.

## Features

- Audio extraction from video files (using ffmpeg)
- Speech-to-text transcription using Faster Whisper (local, fast Whisper implementation)
- Speaker diarization using pyannote-audio (for multi-speaker scenarios)
- Sentiment analysis using VADER or RoBERTa-based models
- Tone intensity analysis using audio amplitude
- Named Entity Recognition (NER) using spaCy
- CSV output with per-segment analysis (speaker, time, transcript, entities, sentiment, tone)
- Interactive visualization interface (Gradio)

## Installation

1. Clone the repository and head over to the folder.
```
git clone https://github.com/humanai-foundation/ISSR.git

Navigate to the project folder
cd ISSR_Communication_Analysis_Tool_Samuel_Kalu
```
## ⚠️ Windows Installation Note

If you are using **Windows**, please avoid Python 3.12.

Some dependencies (e.g., `pandas==2.1.0`) may fail to install due to missing
precompiled wheels and Visual Studio build tools.

### ✅ Recommended Python versions
- Python 3.10
- Python 3.11

After installing a supported Python version, create a virtual environment
and install dependencies again:



2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # or
   source venv/bin/activate  # On Linux/Mac
   ```
3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Download model weights (this is done so as not to clutter up the ISSR repository.):
   ```bash
   python weights_download.py
   ```
   This will automatically download all necessary and extremely heavy model weights into  to your project root.

Since we are using a local model for our transcription (speech-to-text), it requires the command-line tool ffmpeg to be installed on your system, which is available from most package managers:

```
# on Ubuntu or Debian
sudo apt update && sudo apt install ffmpeg

# on Arch Linux
sudo pacman -S ffmpeg

# on MacOS using Homebrew (https://brew.sh/)
brew install ffmpeg

# on Windows using Chocolatey (https://chocolatey.org/)
choco install ffmpeg

# on Windows using Scoop (https://scoop.sh/)
scoop install ffmpeg
```

> [!TIP]
   > ffmpeg is actually platform dependent , so the commands above show the different ways to install it based on your operating system


## Usage


Run the application:
```bash
python app.py
```

Then:
1. Access the web interface on `http://localhost:7860`
2. Either:
   - Enter a folder path containing .mp4 files, or
   - Upload video files directly through the interface




## Architecture

### Data Processing Pipeline

1. **Video Processing (`pipeline.py`)**
   - Handles video file input
   - Acts like a wrapper and Manages the entire processing pipeline and the diarization

2. **Audio Processing (`audio_processing.py`)**
   - Extracts audio from videos (makes use of ffmpeg)
   - Analyzes tone intensity

3. **Transcription (`transcription.py`)**
   - Uses Whisper model for speech-to-text (makes use of ffmpeg also)
   - Segments audio into 5-second chunks

4. **Sentiment Analysis (`sentiment_analysis.py`)**
   - Uses CardiffNLP's RoBERTa model (recently optimized by switching to VADER)
   - Provides sentiment scores (-1 to +1)

5. **Named Entity Recognition (NER) (`ner.py`)**
   - Uses spaCy for extracting entities from transcribed text
   - Identifies names, organizations, locations, and other relevant entities

>[!NOTE]
   >- All tasks  uses a local pre-trained model, zero external APIs or internet connection.
   >- Processing time varies based on video length and system capabilities (GPU or CPU)
   >- CSV outputs are saved with unique names based on input video filenames


## Testing

The system has been tested with:
- Uploading the footage directly
- Loading in the footage directly through a folder.


