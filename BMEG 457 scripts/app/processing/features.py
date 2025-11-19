# RMS, MAV, ZC, WL, mean/variance, EMG feature sets.
import numpy as np

def rms(data):
    return np.sqrt(np.mean(data**2, axis=1, keepdims=True))

def integrated_emg(data):
    return np.sum(np.abs(data), axis=1, keepdims=True)

def mav(data):
    return np.mean(np.abs(data), axis=1, keepdims=True)

# need to calculate metrics now

#relative muscle strength, time to muscle fatigue, activation timing, muscle-cocontraction 