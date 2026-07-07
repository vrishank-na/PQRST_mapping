"""Placeholder for model 1: ECG artefact filtering/noise removal.

The future model should replace `process` with the trained CNN call while
preserving the return shape: {"samples": [...], "fs": 100.0}.
"""

from __future__ import annotations

import numpy as np


DEFAULT_FS = 100.0


def process(ecg_data, fs: float = DEFAULT_FS):
    samples = np.asarray(ecg_data, dtype=float)
    if samples.size == 0:
        raise ValueError("model1 placeholder received no ECG samples")

    baseline = _moving_average(samples, max(5, min(31, samples.size // 8 or 5)))
    denoised = samples - baseline
    denoised = _moving_average(denoised, max(3, min(7, samples.size // 25 or 3)))

    return {
        "samples": denoised.tolist(),
        "fs": float(fs),
        "model": "model1_placeholder",
    }


def _moving_average(samples: np.ndarray, window: int):
    if window <= 1:
        return samples.copy()
    kernel = np.ones(window) / window
    return np.convolve(samples, kernel, mode="same")
