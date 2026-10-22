#!/usr/bin/env python3
"""
AI4MH Unified Pipeline Runner
Orchestrates data processing, word bank generation, sentiment classification,
model evaluation, and interactive crisis prediction.
"""

import os
import sys
import argparse
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

def run_script(script_rel_path: str, extra_args: list = None) -> int:
    """Execute a pipeline script using project Python environment."""
    script_path = os.path.join(PROJECT_ROOT, script_rel_path)
    if not os.path.exists(script_path):
        print(f"❌ Script not found: {script_path}")
        return 1

    cmd = [VENV_PYTHON, script_path] + (extra_args or [])
    print(f"\n▶ Running: {' '.join(cmd)}")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_ROOT}:{env.get('PYTHONPATH', '')}"
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
    return result.returncode

def main():
    parser = argparse.ArgumentParser(
        description="AI4MH Unified Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available stages:
  predict      Run real-time crisis triage CLI (System 1 Gatekeeper)
  wordbank     Extract most frequent keywords from suicidal ideation corpus
  wordcloud    Generate visual mental health word cloud
  sentiment    Run VADER sentiment and heuristic risk assessment
  eval         Evaluate fine-tuned XLM-RoBERTa model on validation split
  all          Run wordbank, wordcloud, sentiment, and model evaluation sequentially
        """
    )
    parser.add_argument(
        "--stage",
        type=str,
        default="predict",
        choices=["predict", "wordbank", "wordcloud", "sentiment", "eval", "all"],
        help="Pipeline stage to execute (default: predict)"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=100,
        help="Number of samples to evaluate when running eval stage (default: 100)"
    )

    args = parser.parse_args()

    stage_map = {
        "predict": [("pipeline/predict.py", [])],
        "wordbank": [("pipeline/generate_word_bank.py", [])],
        "wordcloud": [("pipeline/generate_wordcloud.py", [])],
        "sentiment": [("pipeline/sentiment_risk_classifier.py", [])],
        "eval": [("pipeline/test_model.py", ["--num-samples", str(args.samples)])],
    }

    if args.stage == "all":
        stages_to_run = [
            ("pipeline/generate_word_bank.py", []),
            ("pipeline/generate_wordcloud.py", []),
            ("pipeline/sentiment_risk_classifier.py", []),
            ("pipeline/test_model.py", ["--num-samples", str(args.samples)])
        ]
    else:
        stages_to_run = stage_map[args.stage]

    print("=======================================================")
    print(f"  AI4MH Pipeline Execution: Stage [{args.stage.upper()}]")
    print("=======================================================")

    for script, extra in stages_to_run:
        code = run_script(script, extra)
        if code != 0:
            print(f"\n❌ Pipeline failed during execution of {script} (exit code {code})")
            sys.exit(code)

    print("\n✅ Pipeline stage(s) completed successfully!")

if __name__ == "__main__":
    main()
