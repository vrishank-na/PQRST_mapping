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

    r_indices = _detect_r_peaks(ecg, fs)
    return [{
        "type": "ecg_pqrst",
        "unit": "ms",
        "labels": list(PQRST_LABELS),
        "matrix": _pqrst_windows(r_index, len(ecg), fs),
        "source": "model2_placeholder",
    } for r_index in r_indices]


def _detect_r_peaks(ecg: np.ndarray, fs: float):
    centered = ecg - np.median(ecg)
    if centered.size < 5:
        return [int(np.argmax(centered))]

    threshold = max(float(np.std(centered)), float(np.max(np.abs(centered))) * 0.15, 1e-6)
    peaks = []
    for index in range(1, centered.size - 1):
        if centered[index] > centered[index - 1] and centered[index] >= centered[index + 1]:
            if centered[index] > threshold:
                peaks.append(index)

    if not peaks:
        return [int(np.argmax(centered))]

    min_distance = max(5, int(0.25 * fs))
    filtered_peaks = []
    for peak in peaks:
        if not filtered_peaks or peak - filtered_peaks[-1] >= min_distance:
            filtered_peaks.append(peak)

    return filtered_peaks[:10]


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
