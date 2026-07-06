# placeholder logic for model2
# define pan tompkins algorithm for PQRST detection

import scipy.signal as signal
import numpy as np
import pandas as pd
import csvhandler as csv

filename = "data/intermediateEcg.csv"

def pan_tompkins(ecg_signal, fs):
    # Bandpass filter
    lowcut = 0.5
    highcut = 40.0
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = signal.butter(1, [low, high], btype='band')
    filtered_ecg = signal.filtfilt(b, a, ecg_signal)

    # Derivative filter
    derivative_filter = np.array([1, 2, 0, -2, -1]) / 8.0
    derivative_ecg = np.convolve(filtered_ecg, derivative_filter, mode='same')

    # Squaring function
    squared_ecg = derivative_ecg ** 2

    # Moving window integration
    window_size = int(0.150 * fs)  # 150 ms window
    integrated_ecg = np.convolve(squared_ecg, np.ones(window_size) / window_size, mode='same')

    # Thresholding and peak detection (simplified)
    threshold = np.mean(integrated_ecg) * 1.5
    peaks, _ = signal.find_peaks(integrated_ecg, height=threshold)

    return peaks

# return peaks only in format of PQRST timein timeout, i.e
# {P_start_time, P_end_time}{Q_Start, Q_end}{R_start, R_end}{S_start, R_end}{S_start, S_end}{T_start, T_end}

