import os
import urllib.request
from pathlib import Path

# The official Pyannote AMI RTTM repository
BASE_URLS = [
    "https://raw.githubusercontent.com/pyannote/AMI-diarization-setup/main/only_words/rttms/train/{}.rttm",
    "https://raw.githubusercontent.com/pyannote/AMI-diarization-setup/main/only_words/rttms/dev/{}.rttm",
    "https://raw.githubusercontent.com/pyannote/AMI-diarization-setup/main/only_words/rttms/test/{}.rttm"
]

AUDIO_DIR = Path("screening_notebooks/sample_input_and_output_files")
OBSERVATION_DIR = Path("observations")

def fetch_missing_rttms():
    print("Scanning for audio files that need ground-truth RTTMs...")
    
    # Find all test audio files
    audio_files = [f for f in AUDIO_DIR.glob("*.wav") if "enhanced" not in f.name and "sample_output" not in f.name]
    
    for audio_path in audio_files:
        meeting_id = audio_path.stem
        rttm_path = OBSERVATION_DIR / f"{meeting_id}_ground_truth.rttm"
        
        if rttm_path.exists():
            print(f"[*] Already have ground truth for {meeting_id}")
            continue
            
        print(f"Fetching ground truth for {meeting_id}...")
        success = False
        
        # Try all splits (train/dev/test) to locate the ground truth
        for base_url in BASE_URLS:
            url = base_url.format(meeting_id)
            try:
                urllib.request.urlretrieve(url, str(rttm_path))
                print(f"  [+] Found in {url.split('/')[-2]} split!")
                success = True
                break
            except urllib.error.HTTPError:
                continue
                
        if not success:
            print(f"  [-] Error: Could not find RTTM for {meeting_id} in the official repo.")

if __name__ == "__main__":
    fetch_missing_rttms()
    print("\nAll missing RTTMs have been fetched. You can now run `python evaluate_batch.py` to get full DER metrics for all files!")
