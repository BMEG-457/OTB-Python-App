"""
EMG Fatigue Detection Script for 8x8 High-Density Electrode Array

This script processes EMG data from a CSV file and detects time to fatigue
based on RMS and median frequency analysis.
"""

import numpy as np
import pandas as pd
from scipy import signal
from scipy.fft import rfft, rfftfreq


def bandpass_filter(data, lowcut, highcut, fs, order=4):
    """Apply bandpass filter to EMG signal."""
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = signal.butter(order, [low, high], btype='band')
    return signal.filtfilt(b, a, data, axis=0)


def notch_filter(data, freq, fs, quality=30):
    """Apply notch filter to remove powerline interference."""
    b, a = signal.iirnotch(freq, quality, fs)
    return signal.filtfilt(b, a, data, axis=0)


def rectify_signal(data):
    """Rectify EMG signal (full-wave rectification)."""
    return np.abs(data)


def calculate_rms(data, window_size, step_size):
    """
    Calculate RMS in sliding windows.

    Parameters:
    - data: EMG signal (samples x channels)
    - window_size: window size in samples
    - step_size: step size in samples

    Returns:
    - rms_values: RMS values (windows x channels)
    - window_times: center time of each window
    """
    n_samples = data.shape[0]
    n_channels = data.shape[1] if data.ndim > 1 else 1

    rms_values = []
    window_indices = []

    for start in range(0, n_samples - window_size + 1, step_size):
        end = start + window_size
        window_data = data[start:end]
        rms = np.sqrt(np.mean(window_data**2, axis=0))
        rms_values.append(rms)
        window_indices.append((start + end) // 2)

    return np.array(rms_values), np.array(window_indices)


def calculate_median_frequency(data, fs, window_size, step_size):
    """
    Calculate median frequency in sliding windows using FFT.

    Parameters:
    - data: EMG signal (samples x channels)
    - fs: sampling frequency
    - window_size: window size in samples
    - step_size: step size in samples

    Returns:
    - mf_values: Median frequency values (windows x channels)
    - window_times: center time of each window
    """
    n_samples = data.shape[0]
    n_channels = data.shape[1] if data.ndim > 1 else 1

    mf_values = []
    window_indices = []

    for start in range(0, n_samples - window_size + 1, step_size):
        end = start + window_size
        window_data = data[start:end]

        # Apply Hamming window
        hamming = np.hamming(window_size)
        if data.ndim > 1:
            hamming = hamming[:, np.newaxis]
        windowed_data = window_data * hamming

        # Calculate FFT
        fft_vals = np.abs(rfft(windowed_data, axis=0))
        freqs = rfftfreq(window_size, 1/fs)

        # Calculate median frequency for each channel
        mf_channel = []
        for ch in range(n_channels if data.ndim > 1 else 1):
            if data.ndim > 1:
                power = fft_vals[:, ch]
            else:
                power = fft_vals

            cumsum = np.cumsum(power)
            total_power = cumsum[-1]

            if total_power > 0:
                median_idx = np.where(cumsum >= total_power / 2)[0]
                if len(median_idx) > 0:
                    mf_channel.append(freqs[median_idx[0]])
                else:
                    mf_channel.append(0)
            else:
                mf_channel.append(0)

        mf_values.append(mf_channel if data.ndim > 1 else mf_channel[0])
        window_indices.append((start + end) // 2)

    return np.array(mf_values), np.array(window_indices)


def detect_fatigue(timestamps, rec_data, notch_data, fs,
                   baseline_rms=None,
                   rms_threshold=0.317,  # 31.7% increase
                   mf_threshold=-0.89,   # -0.89 Hz/sec decline
                   window_duration=0.5,  # 500ms windows
                   step_duration=0.1):   # 100ms step
    """
    Calculate time to fatigue based on RMS and median frequency.

    Monitor changes in RMS (increases as fatigue progresses due to increased motor unit recruitment ~20-30%)
    and median frequency (MF) (decreases as fatigue progresses due to slowing of muscle fiber conduction velocity).

    Parameters:
    - timestamps: time array
    - rec_data: rectified/filtered EMG signal
    - notch_data: notch-filtered EMG signal for frequency analysis
    - fs: sampling frequency
    - baseline_rms: baseline RMS value from calibration phase (if None, use first window)
    - rms_threshold: sensitivity for RMS rate of change (31.7% increase in non-athletes during fatigue)
    - mf_threshold: Hz/sec decline threshold for median frequency (-0.89 Hz/sec decline during fatigue)
    - window_duration: window size in seconds
    - step_duration: step size in seconds

    Returns:
    - time_to_rms_fatigue: time array of RMS fatigue onset points (or None)
    - time_to_mf_fatigue: time array of MF fatigue onset points (or None)
    """
    window_size = int(window_duration * fs)
    step_size = int(step_duration * fs)

    # Calculate RMS
    rms_values, rms_indices = calculate_rms(rec_data, window_size, step_size)
    rms_times = timestamps[rms_indices]

    # Calculate baseline RMS if not provided
    if baseline_rms is None:
        baseline_rms = rms_values[0]  # Use first window as baseline

    # Calculate RMS rate of change (percentage increase from baseline)
    if rms_values.ndim > 1:
        rms_change = (rms_values - baseline_rms) / baseline_rms
    else:
        rms_change = (rms_values - baseline_rms) / baseline_rms

    # Calculate Median Frequency
    mf_values, mf_indices = calculate_median_frequency(notch_data, fs, window_size, step_size)
    mf_times = timestamps[mf_indices]

    # Calculate MF rate of change (Hz/sec)
    mf_rate = np.zeros_like(mf_values)
    if len(mf_values) > 1:
        dt = np.diff(mf_times, axis=0)
        dmf = np.diff(mf_values, axis=0)
        if mf_values.ndim > 1:
            dt = dt[:, np.newaxis]
        mf_rate[1:] = dmf / dt

    # Detect RMS fatigue onset (when RMS increase exceeds threshold)
    time_to_rms_fatigue = None
    if rms_values.ndim > 1:
        # For multi-channel, detect when any channel exceeds threshold
        rms_fatigue_mask = np.any(rms_change >= rms_threshold, axis=1)
    else:
        rms_fatigue_mask = rms_change >= rms_threshold

    if np.any(rms_fatigue_mask):
        fatigue_indices = np.where(rms_fatigue_mask)[0]
        time_to_rms_fatigue = rms_times[fatigue_indices]

    # Detect MF fatigue onset (when MF decline rate exceeds threshold)
    time_to_mf_fatigue = None
    if mf_values.ndim > 1:
        # For multi-channel, detect when any channel exceeds threshold
        mf_fatigue_mask = np.any(mf_rate <= mf_threshold, axis=1)
    else:
        mf_fatigue_mask = mf_rate <= mf_threshold

    if np.any(mf_fatigue_mask):
        fatigue_indices = np.where(mf_fatigue_mask)[0]
        time_to_mf_fatigue = mf_times[fatigue_indices]

    return time_to_rms_fatigue, time_to_mf_fatigue


def process_emg_csv(csv_path,
                    fs=2000,  # sampling frequency in Hz
                    lowcut=20,  # bandpass low cutoff
                    highcut=450,  # bandpass high cutoff
                    notch_freq=60,  # powerline frequency
                    baseline_start=0.5,  # baseline window start time in seconds
                    baseline_end=1.0,    # baseline window end time in seconds
                    rms_threshold=0.317,
                    mf_threshold=-0.89,
                    emg_channels=64):  # number of EMG channels (8x8 array = 64)
    """
    Process EMG CSV file and detect fatigue.

    Parameters:
    - csv_path: path to CSV file (first column: timestamp, channels 1-64: EMG data, channels 65-72: auxiliary)
    - fs: sampling frequency
    - lowcut: low cutoff for bandpass filter
    - highcut: high cutoff for bandpass filter
    - notch_freq: notch filter frequency (60 Hz for US, 50 Hz for Europe)
    - baseline_start: baseline window start time in seconds (default 0.5s)
    - baseline_end: baseline window end time in seconds (default 1.0s)
    - rms_threshold: RMS increase threshold (default 31.7%)
    - mf_threshold: MF decline threshold (default -0.89 Hz/sec)
    - emg_channels: number of EMG channels to use (default 64 for 8x8 array)

    Returns:
    - Dictionary with fatigue detection results
    """
    # Load CSV
    print(f"Loading CSV file: {csv_path}")
    df = pd.read_csv(csv_path)

    # Extract timestamps and EMG channel data (columns 1-64, excluding auxiliary channels 65-72)
    timestamps = df.iloc[:, 0].values
    channel_data = df.iloc[:, 1:emg_channels+1].values  # Only EMG channels

    n_samples, n_channels = channel_data.shape
    print(f"Loaded {n_samples} samples across {n_channels} EMG channels")
    print(f"Duration: {timestamps[-1] - timestamps[0]:.2f} seconds")
    print(f"Actual sampling rate: {n_samples / (timestamps[-1] - timestamps[0]):.2f} Hz")

    # Apply bandpass filter
    print("Applying bandpass filter...")
    filtered_data = bandpass_filter(channel_data, lowcut, highcut, fs)

    # Apply notch filter for frequency analysis
    print("Applying notch filter...")
    notch_data = notch_filter(filtered_data, notch_freq, fs)

    # Rectify signal for RMS analysis
    print("Rectifying signal...")
    rec_data = rectify_signal(filtered_data)

    # Calculate baseline RMS from specified window (default 500ms to 1s)
    print(f"Calculating baseline RMS from {baseline_start}s to {baseline_end}s...")
    baseline_start_idx = np.searchsorted(timestamps, baseline_start)
    baseline_end_idx = np.searchsorted(timestamps, baseline_end)
    baseline_data = rec_data[baseline_start_idx:baseline_end_idx]
    baseline_rms = np.sqrt(np.mean(baseline_data**2, axis=0))
    print(f"Baseline calculated from {len(baseline_data)} samples ({baseline_end - baseline_start:.2f}s window)")

    # Detect fatigue
    print("Detecting fatigue...")
    time_to_rms_fatigue, time_to_mf_fatigue = detect_fatigue(
        timestamps, rec_data, notch_data, fs,
        baseline_rms=baseline_rms,
        rms_threshold=rms_threshold,
        mf_threshold=mf_threshold
    )

    # Prepare results
    results = {
        'time_to_rms_fatigue': time_to_rms_fatigue,
        'time_to_mf_fatigue': time_to_mf_fatigue,
        'n_channels': n_channels,
        'n_samples': n_samples,
        'duration': timestamps[-1] - timestamps[0]
    }

    # Print results
    print("\n" + "="*50)
    print("FATIGUE DETECTION RESULTS")
    print("="*50)

    first_rms_fatigue = None
    first_mf_fatigue = None

    if time_to_rms_fatigue is not None and len(time_to_rms_fatigue) > 0:
        first_rms_fatigue = time_to_rms_fatigue[0]
        print(f"\nRMS Fatigue (31.7% increase from baseline):")
        print(f"  First onset: {first_rms_fatigue:.2f} seconds")
        print(f"  Total detections: {len(time_to_rms_fatigue)} time points")
    else:
        print("\nRMS Fatigue: Not detected")

    if time_to_mf_fatigue is not None and len(time_to_mf_fatigue) > 0:
        first_mf_fatigue = time_to_mf_fatigue[0]
        print(f"\nMedian Frequency Fatigue (-0.89 Hz/sec decline):")
        print(f"  First onset: {first_mf_fatigue:.2f} seconds")
        print(f"  Total detections: {len(time_to_mf_fatigue)} time points")
    else:
        print("\nMedian Frequency Fatigue: Not detected")

    # Summary of first fatigue onset
    print("\n" + "="*50)
    print("SUMMARY - TIME TO FATIGUE (FIRST ONSET)")
    print("="*50)

    if first_rms_fatigue is not None or first_mf_fatigue is not None:
        if first_rms_fatigue is not None:
            print(f"RMS Fatigue:         {first_rms_fatigue:.2f} seconds")
        else:
            print(f"RMS Fatigue:         Not detected")

        if first_mf_fatigue is not None:
            print(f"MF Fatigue:          {first_mf_fatigue:.2f} seconds")
        else:
            print(f"MF Fatigue:          Not detected")

        # Determine earliest fatigue indicator
        if first_rms_fatigue is not None and first_mf_fatigue is not None:
            earliest = min(first_rms_fatigue, first_mf_fatigue)
            if earliest == first_rms_fatigue:
                print(f"\nEarliest indicator:  RMS at {earliest:.2f} seconds")
            else:
                print(f"\nEarliest indicator:  MF at {earliest:.2f} seconds")
        elif first_rms_fatigue is not None:
            print(f"\nEarliest indicator:  RMS at {first_rms_fatigue:.2f} seconds")
        elif first_mf_fatigue is not None:
            print(f"\nEarliest indicator:  MF at {first_mf_fatigue:.2f} seconds")
    else:
        print("No fatigue detected in this recording")

    print("="*50)

    return results


def quick_analysis(csv_path, baseline_start=0.5, baseline_end=1.0):
    """
    Quick fatigue analysis with default parameters optimized for
    8x8 HD-EMG array recordings at 2000 Hz.

    This is a convenience function for the standard recording format:
    - Column 0: Timestamp
    - Columns 1-64: EMG data from 8x8 electrode array
    - Columns 65-72: Auxiliary data (ignored)

    Parameters:
    - csv_path: path to recording CSV file
    - baseline_start: baseline window start time in seconds (default 0.5s)
    - baseline_end: baseline window end time in seconds (default 1.0s)

    Returns:
    - Dictionary with fatigue detection results
    """
    return process_emg_csv(
        csv_path,
        fs=2000,
        lowcut=20,
        highcut=450,
        notch_freq=60,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
        rms_threshold=0.317,   # 31.7% increase
        mf_threshold=-0.89,    # -0.89 Hz/sec decline
        emg_channels=64
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("EMG Fatigue Detection for 8x8 HD-EMG Array")
        print("=" * 50)
        print("\nUsage: python fatigue.py <csv_file> [options]")
        print("\nQuick start (recommended):")
        print("  python fatigue.py recording_20260115_122309.csv")
        print("\nAdvanced usage:")
        print("  python fatigue.py <csv_file> [fs] [baseline_start] [baseline_end] [rms_thresh] [mf_thresh]")
        print("\nParameters:")
        print("  csv_file        : Path to CSV file (required)")
        print("  fs              : Sampling frequency in Hz (default: 2000)")
        print("  baseline_start  : Baseline window start in seconds (default: 0.5)")
        print("  baseline_end    : Baseline window end in seconds (default: 1.0)")
        print("  rms_thresh      : RMS increase threshold (default: 0.317 = 31.7%)")
        print("  mf_thresh       : MF decline threshold in Hz/sec (default: -0.89)")
        print("\nExpected CSV format:")
        print("  - Column 0      : Timestamp (seconds)")
        print("  - Columns 1-64  : EMG data from 8x8 array")
        print("  - Columns 65-72 : Auxiliary data (automatically excluded)")
        print("\nBaseline window: 500ms to 1s (default)")
        sys.exit(1)

    csv_path = sys.argv[1]

    # Use default parameters optimized for your recording format
    if len(sys.argv) == 2:
        print("Using optimized default parameters for 8x8 HD-EMG array...")
        print("Baseline window: 0.5s to 1.0s\n")
        results = quick_analysis(csv_path)
    else:
        # Custom parameters
        fs = float(sys.argv[2]) if len(sys.argv) > 2 else 2000
        baseline_start = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
        baseline_end = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
        rms_thresh = float(sys.argv[5]) if len(sys.argv) > 5 else 0.317
        mf_thresh = float(sys.argv[6]) if len(sys.argv) > 6 else -0.89

        results = process_emg_csv(
            csv_path,
            fs=fs,
            baseline_start=baseline_start,
            baseline_end=baseline_end,
            rms_threshold=rms_thresh,
            mf_threshold=mf_thresh,
            emg_channels=64
        )
