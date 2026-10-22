import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipeline.system1_gatekeeper import System1CrisisGatekeeper

# Initialize the System 1 Gatekeeper with the fine-tuned XLM-RoBERTa model
gatekeeper = System1CrisisGatekeeper()

def predict_text(text: str) -> dict:
    """Predict crisis intensity and triage metadata for input text."""
    return gatekeeper.predict(text)

if __name__ == "__main__":
    print("=======================================================")
    print("  Multilingual Mental Health System 1 Crisis Triage    ")
    print("=======================================================")
    print("Type any text or statement to analyze.")
    print("Type 'exit' to quit.\n")
    
    while True:
        try:
            user_input = input("> ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Exiting...")
                break
            
            result = predict_text(user_input)
            print("-" * 55)
            print(f"Intensity Level : {result['intensity_level']} ({result['intensity_name']})")
            print(f"Confidence      : {result['confidence']:.1%}")
            print(f"Crisis Detected : {'YES' if result['is_crisis'] else 'NO'}")
            print(f"Latency         : {result['latency_ms']} ms")
            print(f"Action Protocol : {result['suggested_action']}")
            print("Probability Breakdown:")
            for k, v in result["probabilities"].items():
                print(f"   • {k}: {v * 100:.1f}%")
            print("-" * 55 + "\n")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
