# ML Model architecture for PQRST wave detection and time-seriesification

## ML Model 1
CNN for artefact separation
#### Working flow for model
For training:
```
Residual Input
      │
      ▼
Conv1D (small filters)
      │
ReLU
      │
Conv1D
      │
ReLU
      │
Conv1D
      │
──────────────
Residual Skip Connection
(residual + CNN output)
──────────────
      │
Refined Artefact Output

```

---

## ML Model 2
RNN+LSTM for time-seriesification of processed ECG data.
#### Working flow for model
```
Filtered ECG Window
        │
        ▼
RNN Layer
(learns sample-to-sample transitions)
        │
        ▼
LSTM Layer
(remembers RR interval & rhythm)
        │
        ▼
Dense Layer + Softmax
        │
        ▼
P / QRS / T / Background mask

```