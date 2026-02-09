"""
EMG Burst Duration Analysis
--------------------------
Purpose:
    Detect and quantify the duration of muscle activation bursts (contractions) in EMG recordings.

Workflow:
    1. Load a single-channel EMG CSV file (time, EMG columns).
    2. Preprocess: bandpass filter, rectify, envelope extraction.
    3. Calculate the envelope derivative and establish a baseline from the first 500 ms.
    4. Detect burst onsets and offsets using a dynamic threshold.
    5. Compute burst durations, average duration, and duration variability (std).
    6. Print and visualize the results.

This script is useful for quantifying muscle burst duration in EMG data, e.g., for biomechanics or neurorehabilitation research.
"""

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt
import matplotlib.pyplot as plt

# Helper functions
def bandpass_filter(data, lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data)

def lowpass_filter(data, cutoff, fs, order=4):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low')
    return filtfilt(b, a, data)

# Load CSV
filename = 'BMEG 457 scripts\\tests\\recording_20260115_122054.csv'  # Update this path
fs = 2048  # Set your sampling rate (Hz)

# Read CSV with header, strip whitespace from headers, and coerce non-numeric data to NaN
df = pd.read_csv(filename, header=0, low_memory=False)
df.columns = df.columns.str.strip()
timestamps = pd.to_numeric(df[df.columns[0]], errors='coerce').values
emg = pd.to_numeric(df[df.columns[1]], errors='coerce').values


# Drop any rows with NaN values in timestamps or emg
mask = ~((np.isnan(timestamps)) | (np.isnan(emg)))
timestamps = timestamps[mask]
emg = emg[mask]

# Interpolate timestamps if all are duplicated the same number of times
unique, counts = np.unique(timestamps, return_counts=True)
if len(set(counts)) == 1 and counts[0] > 1:
    n_repeats = counts[0]
    new_timestamps = []
    for i in range(len(unique) - 1):
        interp = np.linspace(unique[i], unique[i+1], n_repeats, endpoint=False)
        new_timestamps.extend(interp)
    last_interval = unique[-1] - unique[-2] if len(unique) > 1 else 1.0
    last_group = np.linspace(unique[-1], unique[-1] + last_interval, n_repeats, endpoint=False)
    new_timestamps.extend(last_group)
    timestamps = np.array(new_timestamps)
    # emg is already in the correct order

# Remove non-increasing timestamps (should not be needed after interpolation, but keep for safety)
unique_mask = np.diff(timestamps, prepend=timestamps[0]) > 0
timestamps = timestamps[unique_mask]
emg = emg[unique_mask]

# Preprocess: bandpass, rectify, envelope
bandpassed_emg = bandpass_filter(emg, 20, 450, fs)
rectified_emg = np.abs(bandpassed_emg)
envelope = lowpass_filter(rectified_emg, 10, fs)

envelope_deriv = np.gradient(envelope, timestamps)

# Baseline from first 500 ms
baseline_mask = timestamps <= (timestamps[0] + 0.5)
baseline_env = envelope[baseline_mask]

# Threshold for burst detection
thresh = np.mean(baseline_env) + 2 * np.std(baseline_env)

# Detect burst onsets and offsets
above = envelope > thresh
# Find rising and falling edges
onsets = np.where(np.diff(above.astype(int)) == 1)[0] + 1
offsets = np.where(np.diff(above.astype(int)) == -1)[0] + 1

# Handle edge cases (burst at start or end)
if above[0]:
    onsets = np.insert(onsets, 0, 0)
if above[-1]:
    offsets = np.append(offsets, len(envelope) - 1)

# Compute burst durations
burst_durations = timestamps[offsets] - timestamps[onsets]

# Remove very short bursts (e.g., < 50 ms)
burst_durations = burst_durations[burst_durations > 0.05]

# Results
num_bursts = len(burst_durations)
avg_duration = np.mean(burst_durations) if num_bursts > 0 else 0
std_duration = np.std(burst_durations) if num_bursts > 0 else 0

print(f"Number of bursts: {num_bursts}")
print(f"Average burst duration: {avg_duration:.3f} s")
print(f"Burst duration variability (std): {std_duration:.3f} s")

# No plotting; results are printed above
