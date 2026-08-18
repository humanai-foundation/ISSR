import os
import urllib.request
from pathlib import Path

# Diverse selection of AMI meetings to test edge cases
# TS: Small team (overlap heavy)
# IN: Different accent/noise profile
# IB: Different room layout
# ES / EN: Standard test sets
MEETINGS_TO_DOWNLOAD = [
    "TS3003a",
    "IN1001",
    "IB4001",
    "ES2003a",
    "EN2001a",
    "IS1000a",
    "TS3007a"
]

BASE_URL = "http://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus/{}/audio/{}.Mix-Headset.wav"
OUTPUT_DIR = Path("screening_notebooks/sample_input_and_output_files")

def download_ami_samples():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"downloading {len(MEETINGS_TO_DOWNLOAD)} ami datasets...")
    print("this may take a while depending on internet speed.\n")
    
    for meeting_id in MEETINGS_TO_DOWNLOAD:
        url = BASE_URL.format(meeting_id, meeting_id)
        output_file = OUTPUT_DIR / f"{meeting_id}.wav"
        
        if output_file.exists():
            print(f"[*] skipping {meeting_id}.wav - already exists.")
            continue
            
        print(f"downloading {meeting_id}.wav...")
        try:
            # Using a basic progress reporter
            def report(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if total_size > 0:
                    percent = downloaded / total_size * 100
                    print(f"\r  progress: {percent:.1f}%", end="")
                    
            urllib.request.urlretrieve(url, str(output_file), reporthook=report)
            print(f"\n[+] successfully downloaded {meeting_id}.wav")
            
        except Exception as e:
            print(f"\n[-] failed to download {meeting_id}: {e}")

if __name__ == "__main__":
    download_ami_samples()
    print("\ndownload complete. run `python evaluate_batch.py` to evaluate.")
    print("note: missing ground truth rttm files will skip der calculation.")
