import os
import glob
import time
from pathlib import Path
from tcamp.pipeline import TCAMPPipeline

import argparse

def generate_markdown_table(results_list, output_file="phase2.5_evaluation_results.md"):
    file_exists = os.path.exists(output_file)
    with open(output_file, 'a') as f:
        if not file_exists:
            f.write("# tcamp batch evaluation results\n\n")
            f.write("| Sample | Condition | Expected Speakers | Actual Speakers | DER | Miss | False Alarm | Confusion | Runtime (s) | Notes |\n")
            f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        
        for res in results_list:
            sample_name = Path(res['input_audio']).stem
            condition = res.get("condition", "Unknown")
            runtime = res.get("runtime", 0.0)
            der_stats = res.get("der_breakdown", {})
            der = res.get("der", 0.0)
            if der is None: der = 0.0
            
            # Count actual speakers detected
            import json
            try:
                with open(res['diarization_results'], 'r') as jf:
                    diarization_data = json.load(jf)
                    actual_speakers = len(set(seg['speaker'] for seg in diarization_data))
            except Exception:
                actual_speakers = "?"
            
            miss = der_stats.get("miss", 0.0) if der_stats else 0.0
            fa = der_stats.get("false_alarm", 0.0) if der_stats else 0.0
            conf = der_stats.get("confusion", 0.0) if der_stats else 0.0
            
            if miss is None: miss = 0.0
            if fa is None: fa = 0.0
            if conf is None: conf = 0.0
            
            notes = "Auto-evaluated"
            if miss > 0.15: notes += " (High Miss Rate)"
            if conf > 0.10: notes += " (High Confusion)"
            if fa > 0.10: notes += " (High FA)"
            
            f.write(f"| {sample_name} | **{condition}** | ? | {actual_speakers} | {der:.2%} | {miss:.2%} | {fa:.2%} | {conf:.2%} | {runtime:.1f} | {notes} |\n")

def main():
    parser = argparse.ArgumentParser(description="run batch evaluation for a specific phase 2.5 condition")
    parser.add_argument("--condition", type=int, choices=[1, 2, 3, 4, 5], required=True, 
                        help="which condition to run (1-5)")
    args = parser.parse_args()

    print(f"starting batch evaluation for condition {args.condition}...")
    pipeline = TCAMPPipeline()
    
    audio_dir = Path("screening_notebooks/sample_input_and_output_files")
    
    # Search for all .wav files in the directory
    # Note: Ensure you run download_ami.py first to populate this directory!
    all_files = [f.name for f in audio_dir.glob("*.wav") if "enhanced" not in f.name and "sample_output" not in f.name]
    
    # 5 Diverse Edge-Case Samples from Part 2 Analysis:
    # EN2002a: High Overlap, Miss Rate jump
    # ES2003a: High Baseline FA
    # IS1000a: Massive FA raw
    # TS3007a: High Miss Rate jump
    # IN1001: Confusion completely solved by DFN
    diverse_selection = ["EN2002a.wav", "ES2003a.wav", "IS1000a.wav", "TS3007a.wav", "IN1001.wav"]
    test_files = [f for f in all_files if f in diverse_selection]

    if not test_files:
        print("no valid ami wav files found. make sure to download them first.")
        return
        
    print(f"found {len(test_files)} diverse files to evaluate: {test_files}")
    
    all_conditions = [
        {"name": "1. Raw -> Pyannote", "phase": "diarize", "method": "deepfilter", "norm": False, "vad": 0.444},
        {"name": "2. DFN -> Default Pyannote", "phase": "all", "method": "deepfilter", "norm": False, "vad": 0.444},
        {"name": "3. DFN -> Lower VAD (0.30)", "phase": "all", "method": "deepfilter", "norm": False, "vad": 0.30},
        {"name": "4. DFN -> Speech Norm -> Default Pyannote", "phase": "all", "method": "deepfilter", "norm": True, "vad": 0.444},
        {"name": "5. DFN -> Speech Norm -> Lower VAD (0.30)", "phase": "all", "method": "deepfilter", "norm": True, "vad": 0.30}
    ]
    
    conditions = [all_conditions[args.condition - 1]]
    
    results = []
    
    # reset diarization pipeline state
    pipeline.diarization_pipeline = None 
    
    for filename in test_files:
        audio_path = audio_dir / filename
        print(f"\n==============================================")
        print(f"evaluating {filename} across all conditions...")
        
        for cond in conditions:
            print(f"\n  -> testing condition: {cond['name']}")
            start_time = time.time()
            try:
                res = pipeline.process(
                    input_audio=audio_path,
                    output_dir="observations/outputs",
                    enhance_method=cond["method"],
                    phase=cond["phase"],
                    apply_normalization=cond["norm"],
                    vad_threshold=cond["vad"]
                )
                res["condition"] = cond["name"]
                res["runtime"] = time.time() - start_time
                results.append(res)
            except Exception as e:
                print(f"error processing {filename} under {cond['name']}: {e}")
                
    print("\ngenerating markdown report...")
    generate_markdown_table(results)
    print("see evaluation_results.md for the tracking table.")

if __name__ == "__main__":
    main()
