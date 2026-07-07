# dsp.py
# Initial ECG cleaning before model 1.

from __future__ import annotations

import numpy as np

try:
    import scipy.signal as signal
except ImportError:  # Keep the dry-run path usable without SciPy installed.
    signal = None


DEFAULT_FS = 100.0


def bandpass_ecg(ecg, fs: float = DEFAULT_FS, lowcut: float = 0.5, highcut: float = 40.0):
    """Bandpass ECG samples, returning a plain list for downstream modules."""
    samples = np.asarray(ecg, dtype=float)
    if samples.size == 0:
        raise ValueError("ECG input is empty")

    if signal is None:
        return _fallback_filter(samples).tolist()

    nyq = 0.5 * fs
    high = min(highcut / nyq, 0.99)
    low = max(lowcut / nyq, 0.001)
    b, a = signal.butter(2, [low, high], btype="band")

    if samples.size > 3 * max(len(a), len(b)):
        filtered = signal.filtfilt(b, a, samples)
    else:
        filtered = signal.lfilter(b, a, samples)

    return filtered.tolist()


def _fallback_filter(samples: np.ndarray):
    """Small moving-average highpass/lowpass fallback for machines without SciPy."""
    baseline_window = max(3, min(25, samples.size // 5 or 3))
    smooth_window = max(3, min(7, samples.size // 20 or 3))
    baseline = _moving_average(samples, baseline_window)
    highpassed = samples - baseline
    return _moving_average(highpassed, smooth_window)


def _moving_average(samples: np.ndarray, window: int):
    if window <= 1:
        return samples.copy()
    kernel = np.ones(window) / window
    return np.convolve(samples, kernel, mode="same")


def subtract_noise(filtered_ecg, baseline_ecg):
    """Return sample-wise residual noise between filtered and baseline ECG."""
    filtered = np.asarray(filtered_ecg, dtype=float)
    baseline = np.asarray(baseline_ecg, dtype=float)
    if filtered.shape != baseline.shape:
        raise ValueError("filtered_ecg and baseline_ecg must have the same length")
    return (filtered - baseline).tolist()
