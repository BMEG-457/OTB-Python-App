"""EMG feature extraction and analysis functions.

This module provides various EMG signal analysis functions including:
- Basic features: RMS, MAV, integrated EMG
- Contraction detection based on RMS rate of change
- Fatigue analysis (time to fatigue via RMS and median frequency)
- Activation timing detection

IMPORTANT: Many functions assume a calibration phase has been completed.
Calibration provides: baseline_rms, threshold, and mvc_rms for each channel.
These calibrated values should be passed as parameters to the analysis functions.

Note: These functions are implemented but not yet fully integrated into the
main application UI. They are available for use in custom analysis scripts
or future UI integration.
"""

from scipy.signal import spectrogram, butter, filtfilt, find_peaks
from dataclasses import dataclass
from typing import Optional
import numpy as np

def rms(data):
    return np.sqrt(np.mean(data**2, axis=1, keepdims=True))

def integrated_emg(data):
    return np.sum(np.abs(data), axis=1, keepdims=True)

def mav(data):
    return np.mean(np.abs(data), axis=1, keepdims=True)

# takes in collection of arrays
def averaged_channels(data): 
    return np.mean(data, axis=0, keepdims=True).T

# EMG Analysis Metrics
# Note: Baseline and threshold values are provided by the calibration phase
# relative muscle strength (shown by the heatmap), time to muscle fatigue (function), activation timing (contraction detection), muscle-cocontraction (idk)

def detect_contractions_rms_rate(rms_data, fs, rate_threshold=0.001, min_duration_samples=5, 
                                 smoothing_window=3, hysteresis_factor=0.6, merge_gap_samples=None):
    """
    Detect muscle contractions based on rate of change in RMS with improved robustness to spikes.
    
    Parameters:
    - rms_data: numpy array of RMS values
    - fs: effective sampling frequency of the RMS data (e.g., fs/window_size)
    - rate_threshold: threshold for rate of change (V/s) to detect contraction onset
    - min_duration_samples: minimum number of samples for a valid contraction
    - smoothing_window: window size for smoothing rate of change (reduces spike sensitivity)
    - hysteresis_factor: offset threshold = hysteresis_factor * rate_threshold (0.5-0.8 recommended)
    - merge_gap_samples: merge contractions separated by fewer samples (None = auto: 0.5 * min_duration)
    
    Returns:
    - contractions: list of tuples (start_time, end_time, peak_rms) for each detected contraction
    """
    # Calculate rate of change of RMS
    drms_dt = np.gradient(rms_data, 1/fs)
    
    # Smooth the rate of change to reduce sensitivity to spikes
    if smoothing_window > 1:
        # Use a moving average to smooth drms_dt
        kernel = np.ones(smoothing_window) / smoothing_window
        drms_dt_smooth = np.convolve(drms_dt, kernel, mode='same')
    else:
        drms_dt_smooth = drms_dt
    
    # Use hysteresis: higher threshold for onset, lower for offset
    onset_threshold = rate_threshold
    offset_threshold = -rate_threshold * hysteresis_factor  # Less negative, harder to trigger offset
    
    # Detect onset points (positive rate of change above threshold)
    onset_mask = drms_dt_smooth > onset_threshold
    
    # Detect offset points (negative rate of change below offset threshold)
    offset_mask = drms_dt_smooth < offset_threshold
    
    # Find contraction periods with improved robustness
    contractions = []
    in_contraction = False
    start_idx = None
    last_offset_idx = -999  # Track last offset to prevent rapid switching
    refractory_period = max(3, int(min_duration_samples * 0.3))  # 30% of min duration
    
    for i in range(len(rms_data)):
        if onset_mask[i] and not in_contraction:
            # Only start new contraction if enough time passed since last offset
            if i - last_offset_idx > refractory_period:
                start_idx = i
                in_contraction = True
        elif offset_mask[i] and in_contraction:
            # Contraction offset detected
            end_idx = i
            duration = end_idx - start_idx
            
            # Only include if duration meets minimum requirement
            if duration >= min_duration_samples:
                start_time = start_idx / fs
                end_time = end_idx / fs
                peak_rms = np.max(rms_data[start_idx:end_idx])
                contractions.append((start_time, end_time, peak_rms))
                last_offset_idx = i
            
            in_contraction = False
            start_idx = None
    
    # Handle case where contraction extends to end of signal
    if in_contraction and start_idx is not None:
        duration = len(rms_data) - start_idx
        if duration >= min_duration_samples:
            start_time = start_idx / fs
            end_time = (len(rms_data) - 1) / fs
            peak_rms = np.max(rms_data[start_idx:])
            contractions.append((start_time, end_time, peak_rms))
    
    # Merge nearby contractions (likely caused by spikes splitting one contraction)
    if len(contractions) > 1:
        if merge_gap_samples is None:
            merge_gap_samples = max(3, int(min_duration_samples * 0.5))
        
        merged = []
        current_start, current_end, current_peak = contractions[0]
        
        for i in range(1, len(contractions)):
            next_start, next_end, next_peak = contractions[i]
            gap_time = next_start - current_end
            gap_samples = int(gap_time * fs)
            
            if gap_samples <= merge_gap_samples:
                # Merge with current contraction
                current_end = next_end
                # Find peak in merged region
                start_idx = int(current_start * fs)
                end_idx = int(current_end * fs)
                current_peak = np.max(rms_data[start_idx:end_idx])
            else:
                # Save current and start new
                merged.append((current_start, current_end, current_peak))
                current_start, current_end, current_peak = next_start, next_end, next_peak
        
        # Add the last contraction
        merged.append((current_start, current_end, current_peak))
        contractions = merged
    
    return contractions
    
def time_to_fatigue_post(rec_data, notch_data, fs, baseline_rms, rms_threshold, mf_threshold):
    """
    Calculate time to fatigue based on RMS and median frequency.
    
    Monitor changes in RMS (increases as fatigue progresses due to increased motor unit recruitment ~20-30%)
    and median frequency (MF) (decreases as fatigue progresses due to slowing of muscle fiber conduction velocity).
    
    Parameters:
    - rec_data: rectified/filtered EMG signal
    - notch_data: notch-filtered EMG signal for frequency analysis
    - fs: sampling frequency
    - baseline_rms: baseline RMS value from calibration phase
    - rms_threshold: sensitivity for RMS rate of change (31.7% increase in non-athletes during fatigue)
    - mf_threshold: Hz/sec decline threshold for median frequency (-0.89 Hz/sec decline during fatigue)
    
    Returns:
    - time_to_rms_fatigue: time array of RMS fatigue onset points (or None)
    - time_to_mf_fatigue: time array of MF fatigue onset points (or None)
    """
    # RMS array calculation
    window_size = 200
    rms_data = np.sqrt(np.convolve(rec_data**2, np.ones(window_size)/window_size, mode='valid'))
    t_rms = np.arange(len(rms_data)) / fs  # time vector for rms
    
    # Use baseline from calibration phase
    # RMS rate of change
    rms_threshold_value = baseline_rms * 1/rms_threshold
    drms = np.gradient(rms_data, 1/fs) 
    rms_indices = np.where(drms > rms_threshold_value)
    
    # Handle empty array case
    if len(rms_indices[0]) > 0:
        time_to_rms_fatigue = t_rms[rms_indices[0]]  # First occurrence
    else:
        time_to_rms_fatigue = None

    # Median frequency calculation with improved implementation
    nperseg = 256
    noverlap = nperseg - 50  # Using overlap for cleaner implementation
    
    f, t_spec, Sxx = spectrogram(notch_data, fs=fs, nperseg=nperseg, noverlap=noverlap)
    
    # Calculate median frequency for each time window
    median_freqs = []
    for i in range(Sxx.shape[1]):
        psd = Sxx[:, i]
        cumsum = np.cumsum(psd)
        cumsum /= cumsum[-1]  # normalize
        mf = np.interp(0.5, cumsum, f)
        median_freqs.append(mf)
    
    median_freqs = np.array(median_freqs)
    times = t_spec

    # Rate of change of median frequency
    dmf = np.gradient(median_freqs, np.mean(np.diff(times)))
    mf_indices = np.where(dmf < mf_threshold)

    # Handle empty array case
    if len(mf_indices) > 0:
        time_to_mf_fatigue = times[mf_indices[0]]  # First occurrence
    else:
        time_to_mf_fatigue = None

    return time_to_rms_fatigue, time_to_mf_fatigue

# activation timing - RETURNS TIME POINTS WHERE ACTIVATION OCCURS BASED ON BASELINE THRESHOLD
def activation_timing_post(rms_data, fs, baseline_threshold): 
    """
    Return time points (seconds) where RMS magnitude exceeds `baseline_threshold`.

    Parameters
    - rms_data: array-like of RMS values (1D or 2D). If multi-dimensional, it will be flattened.
    - fs: sampling frequency in Hz
    - baseline_threshold: scalar threshold to compare RMS against

    Returns
    - numpy.ndarray of times (seconds) where rms > baseline_threshold. May be empty.
    """
    # Ensure a 1-D numpy array
    rms_arr = np.ravel(np.asarray(rms_data))
    t_rms = np.arange(len(rms_arr)) / fs  # time vector for rms

    mask = rms_arr > baseline_threshold
    return t_rms[mask]

# activation timings - RETURNS TRUE IF ACTIVATION OCCURS BASED ON BASELINE THRESHOLD
def activation_timing_live(rms, baseline_threshold):
    # Ensure a 1-D numpy array
    if rms > baseline_threshold:
        return True
    return False

# muscle cocontraction - RETURNS COACTIVATION INDEX BETWEEN TWO MUSCLES


@dataclass
class TKEOResult:
    """Results from TKEO-based activation timing detection."""
    timestamps: np.ndarray
    tkeo_envelope: np.ndarray
    onset_times: np.ndarray
    onset_indices: np.ndarray
    detection_threshold: float
    backtrack_threshold: float
    sample_rate: float


def compute_tkeo_activation_timing(
    raw_signal: np.ndarray,
    timestamps: np.ndarray,
    sample_rate: float,
    bandpass_low: float = 20.0,
    bandpass_high: float = 450.0,
    smooth_cutoff: float = 10.0,
    baseline_duration: float = 0.5,
    k_threshold: float = 8.0,
    amplitude_divisor: float = 4.0,
    min_peak_distance_sec: float = 0.5,
    backtrack_k: float = 3.0,
) -> Optional[TKEOResult]:
    """Detect muscle activation onsets using the Teager-Kaiser Energy Operator (TKEO).

    Takes raw single-channel EMG data, applies full preprocessing pipeline
    (timestamp cleanup, bandpass filter, TKEO, smoothing), and detects onsets
    via statistical thresholding with backtracking.

    Parameters:
        raw_signal: 1D raw EMG signal
        timestamps: 1D timestamp array (same length as raw_signal)
        sample_rate: Estimated sample rate in Hz (used as fallback)
        bandpass_low: Bandpass filter low cutoff (Hz)
        bandpass_high: Bandpass filter high cutoff (Hz)
        smooth_cutoff: Lowpass cutoff for TKEO envelope smoothing (Hz)
        baseline_duration: Duration of quiet baseline period at start (seconds)
        k_threshold: Multiplier for baseline std in detection threshold
        amplitude_divisor: Divisor for amplitude-based threshold (max/divisor)
        min_peak_distance_sec: Minimum distance between detected peaks (seconds)
        backtrack_k: Multiplier for baseline std in backtrack threshold

    Returns:
        TKEOResult with envelope, onset times, and thresholds, or None on failure.
    """
    try:
        signal = raw_signal.copy()
        ts = timestamps.copy()

        # --- Timestamp preprocessing ---
        # Remove NaN entries
        mask = ~(np.isnan(ts) | np.isnan(signal))
        ts = ts[mask]
        signal = signal[mask]

        if len(ts) < 30:
            return None

        # Interpolate duplicated timestamps
        unique, counts = np.unique(ts, return_counts=True)
        if len(set(counts)) == 1 and counts[0] > 1:
            n_repeats = counts[0]
            new_ts = []
            for i in range(len(unique) - 1):
                interp = np.linspace(unique[i], unique[i + 1], n_repeats, endpoint=False)
                new_ts.extend(interp)
            last_interval = unique[-1] - unique[-2] if len(unique) > 1 else 1.0
            last_group = np.linspace(unique[-1], unique[-1] + last_interval, n_repeats, endpoint=False)
            new_ts.extend(last_group)
            ts = np.array(new_ts)

        # Enforce strictly increasing timestamps
        inc_mask = np.diff(ts, prepend=ts[0]) > 0
        ts = ts[inc_mask]
        signal = signal[inc_mask]

        if len(ts) < 30 or np.all(np.diff(ts) == 0):
            return None

        # Re-estimate sample rate from cleaned timestamps
        dt = np.diff(ts)
        dt = dt[dt > 0]
        if len(dt) == 0 or np.median(dt) == 0:
            return None
        fs = 1.0 / np.median(np.diff(ts))

        # --- Bandpass filter (20-450 Hz) ---
        nyq = 0.5 * fs
        if bandpass_high >= nyq:
            bandpass_high = nyq * 0.95
        b, a = butter(4, [bandpass_low / nyq, bandpass_high / nyq], btype='band')
        filtered = filtfilt(b, a, signal)

        # --- Compute TKEO ---
        tkeo = np.zeros(len(filtered))
        tkeo[1:-1] = filtered[1:-1] ** 2 - filtered[:-2] * filtered[2:]
        tkeo[0] = tkeo[1]
        tkeo[-1] = tkeo[-2]

        # --- Rectify ---
        tkeo_rect = np.abs(tkeo)

        # --- Smooth with lowpass filter ---
        b_lp, a_lp = butter(4, smooth_cutoff / nyq, btype='low')
        envelope = filtfilt(b_lp, a_lp, tkeo_rect)

        # --- Baseline from first baseline_duration seconds ---
        baseline_mask = ts <= (ts[0] + baseline_duration)
        baseline_data = envelope[baseline_mask]
        if len(baseline_data) == 0:
            baseline_data = envelope[:int(fs * baseline_duration)]
        baseline_mean = np.mean(baseline_data)
        baseline_std = np.std(baseline_data)

        # --- Detection threshold ---
        stat_threshold = baseline_mean + k_threshold * baseline_std
        amp_threshold = np.max(envelope) / amplitude_divisor
        final_threshold = max(stat_threshold, amp_threshold)

        # --- Find peaks above threshold ---
        min_dist_samples = int(min_peak_distance_sec * fs)
        peak_indices, _ = find_peaks(envelope, height=final_threshold, distance=min_dist_samples)

        # --- Backtrack to find true onset ---
        onset_threshold_low = baseline_mean + backtrack_k * baseline_std
        onset_indices = []
        for peak_idx in peak_indices:
            i = peak_idx
            while i > 0 and envelope[i] > onset_threshold_low:
                i -= 1
            onset_indices.append(i)

        # Deduplicate: multiple peaks can backtrack to the same onset
        onset_indices = np.unique(np.array(onset_indices))
        onset_times = ts[onset_indices] if len(onset_indices) > 0 else np.array([])

        return TKEOResult(
            timestamps=ts,
            tkeo_envelope=envelope,
            onset_times=onset_times,
            onset_indices=onset_indices,
            detection_threshold=final_threshold,
            backtrack_threshold=onset_threshold_low,
            sample_rate=fs,
        )

    except Exception as e:
        print(f"[Features] TKEO activation timing failed: {e}")
        return None

