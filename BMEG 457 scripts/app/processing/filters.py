#low-pass, high-pass, notch, Butterworth, FIR, etc.
import numpy as np
from scipy.signal import butter, filtfilt

def butter_bandpass(data, low, high, fs, order=4):
    b, a = butter(order, [low/fs*2, high/fs*2], btype="band")
    return filtfilt(b, a, data)

def notch(data, freq, fs, quality=30):
    b, a = butter(2, [freq/(fs/2)-freq/(fs/2)/quality, freq/(fs/2)+freq/(fs/2)/quality], btype="bandstop")
    return filtfilt(b, a, data)

def moving_average(data, window_size=5):
    cumsum = np.cumsum(np.insert(data, 0, 0)) 
    return (cumsum[window_size:] - cumsum[:-window_size]) / window_size

def rectify(data):
    return abs(data)

def envelope(data, fs, cutoff=5.0):
    b, a = butter(4, cutoff/(fs/2), btype="low")
    return filtfilt(b, a, abs(data))

