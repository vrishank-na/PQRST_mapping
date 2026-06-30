# dsp.py
# initial cleaning of the ecg, separation of noise for input to model 1

import scipy.signal as signal
from test import FS

# merge highpass, lowpass and bandpass into one helper function, filters
def filters():
    def butter_highpass(cutoff, fs, order=2):
        nyq = 0.5 * fs
        return signal.butter(order, cutoff / nyq, btype='high')

    def butter_lowpass(cutoff, fs, order=2):
        nyq = 0.5 * fs
        return signal.butter(order, cutoff / nyq, btype='low')

    def bandpass_ecg(ecg):
        b_hp, a_hp = butter_highpass(0.5, FS)
        b_lp, a_lp = butter_lowpass(40.0, FS)
        ecg = signal.lfilter(b_hp, a_hp, ecg)
        ecg = signal.lfilter(b_lp, a_lp, ecg)
        return ecg

    return bandpass_ecg

# subtract noise from filtered ecg to get baseline noise to pass as input to model 1
# more convenient than other noise estimation methods
# could also do a log-enhanced method in the future, but won't serve that great
def subtract_noise(bandpass_ecg, baseline_ecg):
    noise = []
    for i in range(len(bandpass_ecg)):
        bandpass_ecg[i] -= baseline_ecg[i]
        noise.append(bandpass_ecg[i])
    return noise