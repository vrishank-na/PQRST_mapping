import numpy as np

def detect_r_peaks(t, v):
    peaks = []

    threshold = np.mean(v) + 0.5 * np.std(v)
    last_peak_t = -1

    for i in range(1, len(v) - 1):
        if v[i] > threshold and v[i] > v[i-1] and v[i] > v[i+1]:
            if last_peak_t < 0 or (t[i] - last_peak_t) > 0.2:
                peaks.append((t[i], v[i]))
                last_peak_t = t[i]

    return peaks
