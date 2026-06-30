import scipy.signal as signal

from test import FS

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