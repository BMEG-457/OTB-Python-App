"""
EMG Onset Detection using Teager-Kaiser Energy Operator (TKEO)
---------------------------------------------------------------
Purpose:
    Detect the onset of muscle contractions using the TKEO method, which is
    sensitive to both amplitude and frequency changes in the signal.

The TKEO is defined as:
    ψ[x(n)] = x(n)² - x(n-1) * x(n+1)

This operator amplifies rapid changes in the signal, making it effective for
detecting sudden muscle activations even with lower amplitude.

Workflow:
    1. Load a single-channel EMG CSV file (time, EMG columns).
    2. Preprocess: bandpass filter the raw signal.
    3. Apply TKEO to the filtered signal.
    4. Smooth the TKEO output with a lowpass filter.
    5. Establish baseline from quiet period and set threshold.
    6. Detect onsets where TKEO exceeds threshold.
    7. Apply refractory period to avoid duplicate detections.
    8. Visualize results.
"""

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks
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


def teager_kaiser_energy(signal):
    """
    Compute the Teager-Kaiser Energy Operator (TKEO).
    ψ[x(n)] = x(n)² - x(n-1) * x(n+1)
    """
    tkeo = np.zeros(len(signal))
    tkeo[1:-1] = signal[1:-1]**2 - signal[:-2] * signal[2:]
    # Handle edges
    tkeo[0] = tkeo[1]
    tkeo[-1] = tkeo[-2]
    return tkeo


# Load CSV
filename = 'BMEG 457 scripts\\tests\\recording_20260115_122309.csv'
df = pd.read_csv(filename, header=0, low_memory=False)
df.columns = df.columns.str.strip()
timestamps = pd.to_numeric(df[df.columns[0]], errors='coerce').values
emg = pd.to_numeric(df[df.columns[1]], errors='coerce').values

# Drop any rows with NaN values
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

# Remove non-increasing timestamps
unique_mask = np.diff(timestamps, prepend=timestamps[0]) > 0
timestamps = timestamps[unique_mask]
emg = emg[unique_mask]

# Check valid timestamps
if len(timestamps) < 2 or np.all(np.diff(timestamps) == 0):
    raise ValueError("Timestamps are not valid for sampling frequency calculation.")

# Estimate sampling frequency
dt = np.diff(timestamps)
dt = dt[dt > 0]
if len(dt) == 0 or np.median(dt) == 0:
    raise ValueError("Timestamps do not allow valid sampling frequency calculation.")
fs = 1 / np.median(np.diff(timestamps))

# --- TKEO-based onset detection ---

# Step 1: Bandpass filter (20-450 Hz)
bandpassed_emg = bandpass_filter(emg, 20, 450, fs)

# Step 2: Apply TKEO
tkeo_signal = teager_kaiser_energy(bandpassed_emg)

# Step 3: Rectify (TKEO can have negative values due to noise)
tkeo_rectified = np.abs(tkeo_signal)

# Step 4: Smooth with lowpass filter (10 Hz envelope)
tkeo_envelope = lowpass_filter(tkeo_rectified, 10, fs)

# Step 5: Establish baseline from first 500 ms
baseline_mask = timestamps <= (timestamps[0] + 0.5)
baseline_tkeo = tkeo_envelope[baseline_mask]
baseline_mean = np.mean(baseline_tkeo)
baseline_std = np.std(baseline_tkeo)

# Step 6: Set threshold (mean + k*std of baseline)
k_threshold = 8  # multiplier for threshold (TKEO values can be large)
onset_threshold = baseline_mean + k_threshold * baseline_std

# Also use an amplitude-based threshold (half max) for comparison
amplitude_thresh = np.max(tkeo_envelope) / 4

# Use the higher of the two thresholds
final_threshold = max(onset_threshold, amplitude_thresh)

# Step 7: Find peaks above threshold
min_peak_distance_sec = 0.5
min_peak_distance = int(min_peak_distance_sec * fs)

peak_indices, _ = find_peaks(
    tkeo_envelope,
    height=final_threshold,
    distance=min_peak_distance
)

# Step 8: Backtrack to find true onset (where TKEO first exceeds a lower threshold)
onset_threshold_low = baseline_mean + 3 * baseline_std
onset_indices = []

for peak_idx in peak_indices:
    # Backtrack from peak until TKEO drops below low threshold
    i = peak_idx
    while i > 0 and tkeo_envelope[i] > onset_threshold_low:
        i -= 1
    onset_indices.append(i)

onset_indices = np.array(onset_indices)
onset_times = timestamps[onset_indices] if len(onset_indices) > 0 else np.array([])

# Also create standard envelope for comparison plot
rectified_emg = np.abs(bandpassed_emg)
standard_envelope = lowpass_filter(rectified_emg, 5, fs)

# --- Plotting ---
fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

# Plot 1: Standard envelope
ax1 = axes[0]
ax1.plot(timestamps, standard_envelope, 'b-', linewidth=1, label='Standard Envelope')
for t in onset_times:
    ax1.axvline(t, color='r', linestyle='--', alpha=0.7)
ax1.set_ylabel('Amplitude')
ax1.set_title('Standard EMG Envelope with TKEO-detected Onsets')
ax1.legend(loc='upper right')

# Plot 2: TKEO envelope
ax2 = axes[1]
ax2.plot(timestamps, tkeo_envelope, 'g-', linewidth=1, label='TKEO Envelope')
ax2.axhline(final_threshold, color='orange', linestyle='-', label=f'Detection Threshold')
ax2.axhline(onset_threshold_low, color='yellow', linestyle='--', label=f'Backtrack Threshold')
for t in onset_times:
    ax2.axvline(t, color='r', linestyle='--', alpha=0.7)
ax2.set_ylabel('TKEO Energy')
ax2.set_title('Teager-Kaiser Energy Operator')
ax2.legend(loc='upper right')

# Plot 3: Raw filtered EMG
ax3 = axes[2]
ax3.plot(timestamps, bandpassed_emg, 'gray', linewidth=0.5, label='Filtered EMG')
for t in onset_times:
    ax3.axvline(t, color='r', linestyle='--', alpha=0.7, label='Onset' if t == onset_times[0] else None)
ax3.set_xlabel('Time (s)')
ax3.set_ylabel('Amplitude')
ax3.set_title('Bandpass Filtered EMG')
ax3.legend(loc='upper right')

plt.tight_layout()
plt.show()

# Print summary
print(f"\n=== TKEO Detection Summary ===")
print(f"Total onsets detected: {len(onset_times)}")
print(f"Onset times (s): {onset_times}")
