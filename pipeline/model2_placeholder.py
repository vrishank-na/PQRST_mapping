"""Placeholder for model 2: PQRST recognition and timing windows."""

from __future__ import annotations

import numpy as np

PQRST_LABELS = ("P", "Q", "R", "S", "T")


def process(model1_output, fs: float | None = None):
    if isinstance(model1_output, dict):
        samples = model1_output.get("samples", [])
        fs = float(model1_output.get("fs", fs or 100.0))
    else:
        samples = model1_output
        fs = float(fs or 100.0)

    ecg = np.asarray(samples, dtype=float)
    if ecg.size == 0:
        raise ValueError("model2 placeholder received no ECG samples")

    r_index = _detect_r_peak(ecg)
    matrix = _pqrst_windows(r_index, len(ecg), fs)

    return [{
        "type": "ecg_pqrst",
        "unit": "ms",
        "labels": list(PQRST_LABELS),
        "matrix": matrix,
        "source": "model2_placeholder",
    }]


def _detect_r_peak(ecg: np.ndarray):
    centered = ecg - np.median(ecg)
    if centered.size >= 20:
        start = int(centered.size * 0.20)
        end = max(start + 1, int(centered.size * 0.90))
        return start + int(np.argmax(centered[start:end]))
    return int(np.argmax(centered))


def _pqrst_windows(r_index: int, sample_count: int, fs: float):
    offsets_ms = {
        "P": (-220, -140),
        "Q": (-60, -20),
        "R": (-20, 35),
        "S": (35, 90),
        "T": (160, 360),
    }
    r_ms = int(round(r_index * 1000.0 / fs))
    duration_ms = int(round(max(sample_count - 1, 0) * 1000.0 / fs))

    absolute = []
    for label in PQRST_LABELS:
        start = _clamp(r_ms + offsets_ms[label][0], 0, duration_ms)
        end = _clamp(r_ms + offsets_ms[label][1], start + 1, duration_ms + 1)
        absolute.append([start, end])

    first_start = absolute[0][0]
    return [[start - first_start, end - first_start] for start, end in absolute]


def _clamp(value: int, low: int, high: int):
    return max(low, min(value, high))
