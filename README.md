# ISSR – AI4MH Yixing Fan Enhance

> Intelligent Skill Sensing & Refinement toolkit for AI4MakersHub (AI4MH) enhancements by Yixing Fan.

---

## 🧭 Quick Navigation

- [Project Overview](#project-overview)
- [Repository Layout](#repository-layout)
- [Environment Setup](#environment-setup)
- [How to Run](#how-to-run)
- [Docs & Tutorials](#docs--tutorials)
- [Contribution Guide](#contribution-guide)
- [License](#license)

---

## Project Overview

ISSR ka goal hai multi-modal sensorimotor skills ko train, evaluate, aur deploy karna—specifically AI4MH workflows (Yixing Fan branch) me refine ki gayi enhancements ke saath. Yeh repo aapko datasets, configs, model checkpoints, aur automation scripts provide karta hai.

Key capabilities:

- Motion & sensor datasets aggregation  
- Config-driven training & evaluation  
- Skill refinement + bridging utilities  
- Visualization aur reporting helpers  

---

## Repository Layout

| Path | Description |
|------|-------------|
| [`docs/`](docs/) | Concept notes, diagrams, research references |
| [`docs/architecture.md`](docs/architecture.md) | System architecture & design details |
| [`docs/tutorials.md`](docs/tutorials.md) | Step-by-step walkthroughs |
| [`configs/`](configs/) | Hydra/YAML configs for training, data, evaluation |
| [`datasets/README.md`](datasets/README.md) | Dataset prep and download instructions |
| [`scripts/`](scripts/) | Automation scripts (`train.py`, `eval.py`, `download_assets.py`, etc.) |
| [`issr/`](issr/) | Core Python package (models, envs, planners, utils) |
| [`notebooks/`](notebooks/) | Analysis & tutorial notebooks |
| [`experiments/`](experiments/) | Logged runs, metrics, and checkpoints |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Contribution process |
| [`LICENSE`](LICENSE) | License info |

---

## Environment Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/humanai-foundation/ISSR.git
   cd ISSR_AI4MH_Yixing_Fan_Enhance
   git lfs install && git lfs pull

How to Run
1. Download assets
bashDownloadCopy codepython scripts/download_assets.py
2. Train / fine-tune
bashDownloadCopy codepython scripts/train.py \
  --config-name base_skill \
  data.path=datasets/aiskill_v2 \
  trainer.max_epochs=120
3. Evaluate
bashDownloadCopy codepython scripts/eval.py \
  --config-name eval_default \
  checkpoint=experiments/latest.ckpt
4. Visualize results
bashDownloadCopy codepython scripts/visualize.py \
  --run-dir experiments/run_2025_01_12
Extra examples: see docs/tutorials.md.

Docs & Tutorials

* 📘 System Architecture
* 🧠 Skill Library Reference
* 📂 Dataset Guide
* 📓 Tutorial Notebooks


Contribution Guide
Open to PRs! Read CONTRIBUTING.md for coding standards, branch naming, aur checklist.

License
Distributed under the MIT License.
