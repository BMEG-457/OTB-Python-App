"""
Bilateral HD-EMG Symmetry Analysis
----------------------------------
Purpose:
    Compare high-density EMG (8x8 array) recordings from the affected and unaffected legs of a stroke patient to assess bilateral muscle activation symmetry.

Workflow:
    1. Load both CSV files (each with 64 channels, 1 per column after time).
    2. Preprocess each channel: bandpass filter, rectify, envelope, normalize.
    3. Extract a feature map (mean envelope per channel, optionally within a contraction window).
    4. Compute a symmetry index (SI) and visualize both legs and their difference.

Symmetry Index (SI) Computation:
    SI = 1 - sum(|A - U|) / sum(A + U)
    Where:
        - A: 8x8 feature map from affected leg
        - U: 8x8 feature map from unaffected leg
    SI ranges from 0 (completely asymmetric) to 1 (perfect symmetry).
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt

# --- Helper functions ---
def bandpass_filter(data, lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data, axis=-1)

def envelope(data, fs, lowpass=10):
    rectified = np.abs(data)
    nyq = 0.5 * fs
    cutoff = lowpass / nyq
    b, a = butter(4, cutoff, btype='low')
    return filtfilt(b, a, rectified, axis=-1)

# --- Load and preprocess function ---
def load_and_preprocess(csv_path, fs):
    df = pd.read_csv(csv_path, header=0)
    # Assume first column is time, next 64 are channels
    data = df.iloc[:, 1:65].values.T  # shape: (64, time)
    # Bandpass filter
    filtered = bandpass_filter(data, 20, 450, fs)
    # Envelope
    env = envelope(filtered, fs)
    # Normalize (per channel)
    env_norm = env / np.max(env, axis=1, keepdims=True)
    return env_norm, df.iloc[:, 0].values  # (64, time), time

# --- Feature extraction (mean envelope during contraction) ---
def extract_feature(env, time, window=None):
    # window: (start, end) in seconds
    if window is not None:
        mask = (time >= window[0]) & (time <= window[1])
        feat = np.mean(env[:, mask], axis=1)
    else:
        feat = np.mean(env, axis=1)
    return feat.reshape(8, 8)

# --- Symmetry index ---
def symmetry_index(A, U):
    return 1 - np.sum(np.abs(A - U)) / np.sum(A + U)

# --- Main workflow ---
# User: set these paths and sampling rate
csv_affected = 'BMEG 457 scripts\\tests\\recording_20260115_114648.csv'
csv_unaffected = 'BMEG 457 scripts\\tests\\recording_20260115_122152.csv'
fs = 2048  # Set your sampling rate (Hz)

# Load and preprocess
env_aff, time_aff = load_and_preprocess(csv_affected, fs)
env_unaff, time_unaff = load_and_preprocess(csv_unaffected, fs)

# (Optional) Set contraction window in seconds, e.g., (2, 4)
window = None  # or (start, end)

# Extract features
feat_aff = extract_feature(env_aff, time_aff, window)
feat_unaff = extract_feature(env_unaff, time_unaff, window)

# Compute symmetry index
si = symmetry_index(feat_aff, feat_unaff)
print(f'Symmetry Index: {si:.3f}')

# --- Visualization ---
fig, axs = plt.subplots(1, 3, figsize=(15, 5))
axs[0].imshow(feat_aff, cmap='hot', aspect='auto')
axs[0].set_title('Affected Leg')
axs[1].imshow(feat_unaff, cmap='hot', aspect='auto')
axs[1].set_title('Unaffected Leg')
axs[2].imshow(np.abs(feat_aff - feat_unaff), cmap='bwr', aspect='auto')
axs[2].set_title('Absolute Difference')
for ax in axs:
    ax.axis('off')
plt.suptitle(f'Bilateral Symmetry Index: {si:.3f}')
plt.tight_layout()
plt.show()
