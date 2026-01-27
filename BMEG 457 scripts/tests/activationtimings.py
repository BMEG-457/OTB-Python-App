"""
EMG Onset Detection and Timing Analysis
--------------------------------------
Purpose:
    Detect the onset of muscle contractions in EMG recordings using envelope and derivative thresholding.

Workflow:
    1. Load a single-channel EMG CSV file (time, EMG columns).
    2. Preprocess: bandpass filter, rectify, envelope extraction.
    3. Calculate the envelope derivative and establish a baseline from the first 500 ms.
    4. Detect onsets where the derivative exceeds a dynamic threshold.
    5. Backtrack to find the true onset, requiring a pre-onset baseline and a minimum envelope rise.
    6. Enforce a minimum interval between onsets (refractory period).
    7. Visualize the envelope with detected onsets overlaid.

This script is useful for quantifying muscle activation timing in EMG data, e.g., for biomechanics or neurorehabilitation research.
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
filename = 'C:\\Users\\Nicholas\\Downloads\\15_01_26_recordings\\recordings\\ellie\\recording_20260115_122054.csv'
# Read CSV with header, strip whitespace from headers, and coerce non-numeric data to NaN
df = pd.read_csv(filename, header=0, low_memory=False)
df.columns = df.columns.str.strip()  # Remove any whitespace from column names
# Replace 'Timestamp' and 'EMG' with your actual column names if different
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
        # Interpolate between unique[i] and unique[i+1]
        interp = np.linspace(unique[i], unique[i+1], n_repeats, endpoint=False)
        new_timestamps.extend(interp)
    # For the last group, extrapolate using the last interval
    last_interval = unique[-1] - unique[-2] if len(unique) > 1 else 1.0
    last_group = np.linspace(unique[-1], unique[-1] + last_interval, n_repeats, endpoint=False)
    new_timestamps.extend(last_group)
    timestamps = np.array(new_timestamps)
    # emg is already in the correct order

# Remove non-increasing timestamps (should not be needed after interpolation, but keep for safety)
unique_mask = np.diff(timestamps, prepend=timestamps[0]) > 0
timestamps = timestamps[unique_mask]
emg = emg[unique_mask]

# Check if we have enough valid timestamps
if len(timestamps) < 2 or np.all(np.diff(timestamps) == 0):
    raise ValueError("Timestamps are not valid for sampling frequency calculation. Check your CSV data.")

# Estimate sampling frequency
dt = np.diff(timestamps)
dt = dt[dt > 0]  # Only positive intervals
if len(dt) == 0 or np.median(dt) == 0:
    raise ValueError("Timestamps do not allow valid sampling frequency calculation (zero or negative intervals). Check your CSV data.")
fs = 1 / np.median(dt)

# Estimate sampling frequency
fs = 1 / np.median(np.diff(timestamps))



# Step 1: Bandpass filter (20-450 Hz) on raw signal
bandpassed_emg = bandpass_filter(emg, 20, 450, fs)

# Step 2: Rectify the bandpassed signal
rectified_emg = np.abs(bandpassed_emg)


# Step 3: Envelope (10 Hz lowpass) on rectified signal
envelope = lowpass_filter(rectified_emg, 5, fs)

# --- Trigger Detection Steps ---
# 1. Calculate derivative of the envelope
envelope_deriv = np.gradient(envelope, timestamps)

# 2. Establish baseline from first 500 ms for both envelope and derivative
baseline_mask = timestamps <= (timestamps[0] + 0.5)
baseline_env = envelope[baseline_mask]
baseline_deriv = envelope_deriv[baseline_mask]

# 3. Find triggers: points where derivative exceeds mean + 3*std of baseline derivative
thresh = np.mean(baseline_deriv) + 3 * np.std(baseline_deriv)
trigger_mask = envelope_deriv > thresh


# 4. Remove duplicates: skip detections within 500 ms of each other
trigger_indices = np.where(trigger_mask)[0]
if len(trigger_indices) > 0:
    trigger_times = timestamps[trigger_indices]
    # Only keep triggers separated by at least 500 ms
    filtered_indices = [trigger_indices[0]]
    for idx in trigger_indices[1:]:
        if timestamps[idx] - timestamps[filtered_indices[-1]] >= 0.3:
            filtered_indices.append(idx)
    filtered_indices = np.array(filtered_indices)
else:
    filtered_indices = np.array([])

# --- Backtracking to find true onset, with pre-onset baseline check and post-onset envelope rise check ---
onset_indices = []
if len(filtered_indices) > 0:
    baseline_env_mean = np.mean(baseline_env)
    baseline_env_std = np.std(baseline_env)
    env_thresh = baseline_env_mean + 1 * baseline_env_std  # threshold for envelope backtracking
    pre_window = 0.05  # seconds to check before onset (e.g., 50 ms)
    post_window = 0.05  # seconds to check after onset (e.g., 150 ms)
    min_rise = 0.5 * baseline_env_std  # minimum envelope rise after onset
    for idx in filtered_indices:
        # Backtrack until envelope derivative falls below baseline mean or envelope falls below threshold
        i = idx
        while i > 0 and (envelope_deriv[i] > np.mean(baseline_deriv) or envelope[i] > env_thresh):
            i -= 1
        # Require envelope to be below threshold for pre_window before i
        pre_idx = np.where((timestamps >= timestamps[i] - pre_window) & (timestamps < timestamps[i]))[0]
        # Require envelope to rise by min_rise within post_window after i
        post_idx = np.where((timestamps > timestamps[i]) & (timestamps <= timestamps[i] + post_window))[0]
        if (
            len(pre_idx) > 0 and np.all(envelope[pre_idx] < env_thresh)
            and len(post_idx) > 0 and (np.max(envelope[post_idx]) - envelope[i] > min_rise)
        ):
            onset_indices.append(i)
    onset_indices = np.array(onset_indices)
    onset_times = timestamps[onset_indices]
else:
    onset_times = np.array([])

# Plot envelope and overlay detected onsets as vertical lines
plt.figure(figsize=(12, 6))
plt.plot(timestamps, envelope, label='Envelope (10 Hz Lowpass)', linewidth=2)
for t in onset_times:
    plt.axvline(t, color='r', linestyle='--', label='Onset' if t == onset_times[0] else None)
plt.title('EMG Envelope with Detected Onsets (Backtracked)')
plt.xlabel('Time (s)')
plt.ylabel('Amplitude')
if len(onset_times) > 0:
    plt.legend()
plt.tight_layout()
plt.show()