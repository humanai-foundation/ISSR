import pandas as pd
import torch
from transformers import BertTokenizer, BertForSequenceClassification, Trainer
from datasets import Dataset
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, roc_auc_score

# 1. Load model and tokenizer
model_path = "results/final_model"
model = BertForSequenceClassification.from_pretrained(model_path)
tokenizer = BertTokenizer.from_pretrained(model_path)

# 2. Load validation dataset
df = pd.read_csv("dataset/Suicidal Ideation Detection Reddit Dataset-Version 2.csv")
df = df.dropna(subset=["Post"])
df["Label"] = df["Label"].apply(lambda x: 1 if x.lower() == "suicidal" else 0)

# Use 10% of data as validation set
val_texts = df["Post"].tolist()[-1000:]
val_labels = df["Label"].tolist()[-1000:]

def tokenize_function(examples):
    return tokenizer(examples["text"], padding="max_length", truncation=True)

val_dataset = Dataset.from_dict({"text": val_texts, "label": val_labels})
val_dataset = val_dataset.map(tokenize_function, batched=True)
val_dataset.set_format(type="torch", columns=["input_ids", "attention_mask", "label"])

# 3. Define metrics
def compute_metrics(pred):
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)
    probs = torch.softmax(torch.tensor(pred.predictions), dim=1)[:, 1].numpy()
    roc_auc = roc_auc_score(labels,probs)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average="binary")
    acc = accuracy_score(labels, preds)
    return {"accuracy": acc, "f1": f1, "precision": precision, "recall": recall , "roc_auc": roc_auc}

trainer = Trainer(model=model, tokenizer=tokenizer)
preds = trainer.predict(val_dataset)
print(compute_metrics(preds))
