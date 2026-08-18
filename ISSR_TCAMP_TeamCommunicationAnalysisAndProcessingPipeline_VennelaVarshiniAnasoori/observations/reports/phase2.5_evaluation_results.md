# tcamp batch evaluation results

| Sample | Condition | Expected Speakers | Actual Speakers | DER | Miss | False Alarm | Confusion | Runtime (s) | Notes |
|---|---|---|---|---|---|---|---|---|---|
| EN2002a | **1. Raw -> Pyannote** | ? | 5 | 24.73% | 13.39% | 2.86% | 8.49% | 2171.6 | Auto-evaluated |
| ES2003a | **1. Raw -> Pyannote** | ? | 4 | 11.41% | 4.52% | 4.03% | 2.85% | 1113.3 | Auto-evaluated |
| IN1001 | **1. Raw -> Pyannote** | ? | 7 | 15.49% | 6.39% | 3.99% | 5.11% | 2718.7 | Auto-evaluated |
| IS1000a | **1. Raw -> Pyannote** | ? | 5 | 25.75% | 10.58% | 9.79% | 5.38% | 1212.3 | Auto-evaluated |
| TS3007a | **1. Raw -> Pyannote** | ? | 6 | 19.60% | 6.63% | 6.51% | 6.46% | 1236.3 | Auto-evaluated |
| EN2002a | **2. DFN -> Default Pyannote** | ? | 6 | 30.73% | 23.76% | 1.18% | 5.78% | N/A | Auto-evaluated |
| ES2003a | **2. DFN -> Default Pyannote** | ? | 7 | 15.20% | 8.24% | 2.60% | 4.36% | N/A | Auto-evaluated |
| IN1001 | **2. DFN -> Default Pyannote** | ? | 4 | 17.08% | 12.65% | 2.08% | 2.35% | N/A | Auto-evaluated |
| IS1000a | **2. DFN -> Default Pyannote** | ? | 9 | 33.10% | 18.64% | 5.61% | 8.85% | N/A | Auto-evaluated |
| TS3007a | **2. DFN -> Default Pyannote** | ? | 6 | 28.03% | 17.06% | 3.47% | 7.49% | N/A | Auto-evaluated |
| EN2002a | **3. DFN -> Lower VAD (0.30)** | ? | 6 | 31.01% | 24.14% | 1.17% | 5.71% | 2134.3 | Auto-evaluated (High Miss Rate) |
| ES2003a | **3. DFN -> Lower VAD (0.30)** | ? | 9 | 15.15% | 7.70% | 2.66% | 4.79% | 1123.9 | Auto-evaluated |
| IN1001 | **3. DFN -> Lower VAD (0.30)** | ? | 4 | 17.12% | 12.69% | 2.12% | 2.31% | 3405.8 | Auto-evaluated |
| IS1000a | **3. DFN -> Lower VAD (0.30)** | ? | 8 | 32.57% | 18.42% | 5.61% | 8.53% | 1548.4 | Auto-evaluated (High Miss Rate) |
| TS3007a | **3. DFN -> Lower VAD (0.30)** | ? | 6 | 30.50% | 19.27% | 3.47% | 7.77% | 1561.8 | Auto-evaluated (High Miss Rate) |
| EN2002a | **4. DFN -> Speech Norm -> Default Pyannote** | ? | 7 | 37.89% | 24.86% | 1.12% | 11.91% | 2081.1 | Auto-evaluated (High Miss Rate) (High Confusion) |
| ES2003a | **4. DFN -> Speech Norm -> Default Pyannote** | ? | 6 | 26.19% | 8.83% | 2.48% | 14.88% | 1092.4 | Auto-evaluated (High Confusion) |
| IN1001 | **4. DFN -> Speech Norm -> Default Pyannote** | ? | 6 | 25.19% | 16.30% | 2.09% | 6.79% | 3352.7 | Auto-evaluated (High Miss Rate) |
| IS1000a | **4. DFN -> Speech Norm -> Default Pyannote** | ? | 8 | 40.36% | 17.07% | 6.93% | 16.36% | 1488.5 | Auto-evaluated (High Miss Rate) (High Confusion) |
| TS3007a | **4. DFN -> Speech Norm -> Default Pyannote** | ? | 6 | 38.48% | 20.59% | 3.24% | 14.66% | 1492.2 | Auto-evaluated (High Miss Rate) (High Confusion) |
| EN2002a | **5. DFN -> Speech Norm -> Lower VAD (0.30)** | ? | 7 | 37.89% | 24.86% | 1.12% | 11.91% | 2119.4 | Auto-evaluated (High Miss Rate) (High Confusion) |
| ES2003a | **5. DFN -> Speech Norm -> Lower VAD (0.30)** | ? | 6 | 26.19% | 8.83% | 2.48% | 14.88% | 1197.0 | Auto-evaluated (High Confusion) |
| IN1001 | **5. DFN -> Speech Norm -> Lower VAD (0.30)** | ? | 6 | 25.19% | 16.30% | 2.09% | 6.79% | 4474.6 | Auto-evaluated (High Miss Rate) |
| IS1000a | **5. DFN -> Speech Norm -> Lower VAD (0.30)** | ? | 8 | 40.36% | 17.07% | 6.93% | 16.36% | 1515.4 | Auto-evaluated (High Miss Rate) (High Confusion) |
| TS3007a | **5. DFN -> Speech Norm -> Lower VAD (0.30)** | ? | 6 | 38.48% | 20.59% | 3.24% | 14.66% | 1535.2 | Auto-evaluated (High Miss Rate) (High Confusion) |
