import os
import sys
import argparse
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer
from datasets import Dataset
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SYSTEM1 = os.path.join(BASE_DIR, "results", "xlm_roberta_system1")
DEFAULT_FINAL = os.path.join(BASE_DIR, "results", "final_model")
DEFAULT_DATASET = os.path.join(BASE_DIR, "dataset", "Suicidal Ideation Detection Reddit Dataset-Version 2.csv")

def find_best_model_dir() -> str:
    """Return model directory with existing weights if available."""
    for candidate in (DEFAULT_SYSTEM1, DEFAULT_FINAL):
        if os.path.exists(candidate) and any(
            os.path.exists(os.path.join(candidate, w)) for w in ("model.safetensors", "pytorch_model.bin")
        ):
            return candidate
    return DEFAULT_SYSTEM1

def main():
    parser = argparse.ArgumentParser(description="Evaluate fine-tuned classification model")
    parser.add_argument(
        "--model-path",
        type=str,
        default=None,
        help="Path to trained model directory (default: auto-detect xlm_roberta_system1 or final_model)"
    )
    parser.add_argument(
        "--dataset-path",
        type=str,
        default=DEFAULT_DATASET,
        help="Path to evaluation dataset CSV"
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=100,
        help="Number of validation samples to evaluate (default: 100 for fast eval)"
    )
    args = parser.parse_args()

    model_path = args.model_path or find_best_model_dir()

    if not os.path.exists(model_path):
        print(f"❌ Model path '{model_path}' does not exist.")
        sys.exit(1)

    has_weights = any(
        os.path.exists(os.path.join(model_path, w)) for w in ("model.safetensors", "pytorch_model.bin")
    )
    if not has_weights:
        print(f"⚠️  No model weights ('model.safetensors' or 'pytorch_model.bin') found in '{model_path}'.")
        print("   Please ensure trained weights are placed in this directory before running evaluation.")
        sys.exit(1)

    if not os.path.exists(args.dataset_path):
        print(f"❌ Dataset not found at: {args.dataset_path}")
        sys.exit(1)

    print(f"📥 Loading model and tokenizer from: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    num_labels = model.config.num_labels
    print(f"   Architecture: {model.config.model_type} ({num_labels} classification classes)")

    print(f"📂 Loading validation dataset from: {args.dataset_path}")
    df = pd.read_csv(args.dataset_path)
    text_col = "Post" if "Post" in df.columns else df.columns[0]
    label_col = "Label" if "Label" in df.columns else df.columns[-1]

    df = df.dropna(subset=[text_col])
    
    # Map binary or categorical labels
    if num_labels == 2:
        df["label_numeric"] = df[label_col].apply(lambda x: 1 if str(x).strip().lower() == "suicidal" else 0)
    else:
        # Multi-class fallback mapping
        label_mapping = {"safe": 0, "mild": 1, "moderate": 2, "crisis": 3, "suicidal": 3, "non-suicidal": 0}
        df["label_numeric"] = df[label_col].apply(lambda x: label_mapping.get(str(x).strip().lower(), 0))

    sample_size = min(len(df), args.num_samples)
    val_df = df.tail(sample_size)
    val_texts = val_df[text_col].astype(str).tolist()
    val_labels = val_df["label_numeric"].tolist()

    def tokenize_function(examples):
        return tokenizer(examples["text"], padding="max_length", truncation=True, max_length=128)

    val_dataset = Dataset.from_dict({"text": val_texts, "label": val_labels})
    val_dataset = val_dataset.map(tokenize_function, batched=True)
    val_dataset.set_format(type="torch", columns=["input_ids", "attention_mask", "label"])

    def compute_metrics(pred):
        labels = pred.label_ids
        preds = pred.predictions.argmax(-1)
        avg_mode = "binary" if num_labels == 2 else "weighted"
        precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average=avg_mode, zero_division=0)
        acc = accuracy_score(labels, preds)
        return {
            "accuracy": round(float(acc), 4),
            "f1": round(float(f1), 4),
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4)
        }

    print("📊 Evaluating model on validation samples...")
    import inspect
    trainer_kwargs = {"model": model}
    if "processing_class" in inspect.signature(Trainer.__init__).parameters:
        trainer_kwargs["processing_class"] = tokenizer
    else:
        trainer_kwargs["tokenizer"] = tokenizer

    trainer = Trainer(**trainer_kwargs)
    preds = trainer.predict(val_dataset)
    metrics = compute_metrics(preds)

    print("\n================ Evaluation Results ================")
    for k, v in metrics.items():
        print(f"  {k.capitalize():<12}: {v:.4f}")
    print("====================================================\n")

if __name__ == "__main__":
    main()
