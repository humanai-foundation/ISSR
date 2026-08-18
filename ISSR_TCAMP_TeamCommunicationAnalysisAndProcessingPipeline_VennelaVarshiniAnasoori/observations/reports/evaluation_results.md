# TCAMP Batch Evaluation Results

> [!NOTE]
> Phase 1 and Phase 2 baseline results are recorded here. For the Phase 2.5 (Tuning & Normalization) ablation study, please see `observations/phase2.5_validation.md`.

| Sample | Condition | Expected Speakers | Actual Speakers | DER | Miss | False Alarm | Confusion | Notes |
|---|---|---|---|---|---|---|---|---|
| EN2001a | **Raw** | ? | 7 | 8.26% | 3.85% | 2.14% | 2.27% | Auto-evaluated |
| EN2001a | **NoiseReduce** | ? | 10 | 21.00% | 9.06% | 2.81% | 9.13% | Auto-evaluated |
| EN2001a | **DeepFilterNet** | ? | 8 | 10.96% | 6.96% | 1.62% | 2.39% | Auto-evaluated |
| EN2002a | **Raw** | ? | 5 | 24.73% | 13.39% | 2.86% | 8.48% | Auto-evaluated |
| EN2002a | **NoiseReduce** | ? | 4 | 56.45% | 28.60% | 1.26% | 26.59% | Auto-evaluated (High Miss Rate) (High Confusion) |
| EN2002a | **DeepFilterNet** | ? | 6 | 30.73% | 23.76% | 1.18% | 5.78% | Auto-evaluated (High Miss Rate) |
| ES2003a | **Raw** | ? | 4 | 11.41% | 4.52% | 4.03% | 2.85% | Auto-evaluated |
| ES2003a | **NoiseReduce** | ? | 2 | 60.04% | 10.61% | 3.51% | 45.93% | Auto-evaluated (High Confusion) |
| ES2003a | **DeepFilterNet** | ? | 7 | 15.20% | 8.24% | 2.60% | 4.36% | Auto-evaluated |
| ES2004a | **Raw** | ? | 5 | 19.36% | 12.43% | 3.21% | 3.73% | Auto-evaluated |
| ES2004a | **NoiseReduce** | ? | 5 | 24.39% | 19.29% | 2.40% | 2.70% | Auto-evaluated (High Miss Rate) |
| ES2004a | **DeepFilterNet** | ? | 7 | 25.11% | 19.46% | 2.02% | 3.63% | Auto-evaluated (High Miss Rate) |
| IB4001 | **Raw** | ? | 5 | 18.71% | 6.54% | 5.33% | 6.83% | Auto-evaluated |
| IB4001 | **NoiseReduce** | ? | 3 | 52.49% | 12.54% | 3.32% | 36.63% | Auto-evaluated (High Confusion) |
| IB4001 | **DeepFilterNet** | ? | 7 | 23.07% | 13.29% | 3.16% | 6.62% | Auto-evaluated |
| IN1001 | **Raw** | ? | 7 | 15.49% | 6.39% | 3.99% | 5.11% | Auto-evaluated |
| IN1001 | **NoiseReduce** | ? | 4 | 53.40% | 21.07% | 1.63% | 30.70% | Auto-evaluated (High Miss Rate) (High Confusion) |
| IN1001 | **DeepFilterNet** | ? | 4 | 17.08% | 12.65% | 2.08% | 2.35% | Auto-evaluated |
| IS1000a | **Raw** | ? | 5 | 25.75% | 10.58% | 9.79% | 5.38% | Auto-evaluated |
| IS1000a | **NoiseReduce** | ? | 4 | 47.80% | 20.65% | 4.72% | 22.43% | Auto-evaluated (High Miss Rate) (High Confusion) |
| IS1000a | **DeepFilterNet** | ? | 9 | 33.10% | 18.64% | 5.61% | 8.85% | Auto-evaluated (High Miss Rate) |
| IS1009a | **Raw** | ? | 5 | 20.38% | 8.57% | 5.56% | 6.25% | Auto-evaluated |
| IS1009a | **NoiseReduce** | ? | 3 | 38.00% | 15.01% | 4.87% | 18.12% | Auto-evaluated (High Miss Rate) (High Confusion) |
| IS1009a | **DeepFilterNet** | ? | 6 | 24.88% | 16.04% | 3.37% | 5.47% | Auto-evaluated (High Miss Rate) |
| sample_input | **Raw** | ? | 3 | 509.61% | 2.34% | 507.26% | 0.00% | Auto-evaluated (High FA) |
| sample_input | **NoiseReduce** | ? | 3 | 512.91% | 18.15% | 494.76% | 0.00% | Auto-evaluated (High Miss Rate) (High FA) |
| sample_input | **DeepFilterNet** | ? | 3 | 507.34% | 2.68% | 504.61% | 0.06% | Auto-evaluated (High FA) |
| sample_noisy | **Raw** | ? | 4 | 0.00% | 0.00% | 0.00% | 0.00% | Auto-evaluated (No Ground Truth) |
| sample_noisy | **NoiseReduce** | ? | 2 | 0.00% | 0.00% | 0.00% | 0.00% | Auto-evaluated (No Ground Truth) |
| sample_noisy | **DeepFilterNet** | ? | 2 | 0.00% | 0.00% | 0.00% | 0.00% | Auto-evaluated (No Ground Truth) |
| TS3003a | **Raw** | ? | 3 | 18.17% | 11.48% | 2.80% | 3.89% | Auto-evaluated |
| TS3003a | **NoiseReduce** | ? | 4 | 27.43% | 22.07% | 2.05% | 3.30% | Auto-evaluated (High Miss Rate) |
| TS3003a | **DeepFilterNet** | ? | 6 | 24.33% | 19.87% | 1.27% | 3.19% | Auto-evaluated (High Miss Rate) |
| TS3007a | **Raw** | ? | 6 | 19.60% | 6.63% | 6.51% | 6.46% | Auto-evaluated |
| TS3007a | **NoiseReduce** | ? | 3 | 43.13% | 13.16% | 4.75% | 25.23% | Auto-evaluated (High Confusion) |
| TS3007a | **DeepFilterNet** | ? | 6 | 28.03% | 17.06% | 3.47% | 7.49% | Auto-evaluated (High Miss Rate) |
