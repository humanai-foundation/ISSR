# AI4MH Model Checkpoints & System 1 Weights

This directory houses the weights and configuration artifacts for the fine-tuned Mental Health Crisis Triage models.

## Current Primary Model: Multilingual System 1 Crisis Gatekeeper

* **Backbone:** `FacebookAI/xlm-roberta-base` (278M parameters, 100+ languages)
* **Location:** `results/xlm_roberta_system1/`
* **Performance:** 80.17% Test Accuracy, 80.21% Weighted F1
* **Latency:** < 90ms CPU inference

### Weight Files:
- `config.json`: Architecture hyperparameters and label configuration (4 ordinal intensity tiers).
- `tokenizer.json` & `tokenizer_config.json`: SentencePiece multilingual tokenizer assets.
- `model.safetensors` (1.1 GB): Fine-tuned classification head & transformer weights. Note that due to GitHub's file size threshold (>100MB), the binary weights are stored via Git LFS / cloud release mirror.

## Legacy Model: BERT Binary Classifier
- `results/final_model/`: Checkpoint metadata for the earlier prototype binary ideation model.
