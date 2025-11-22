# RMS, MAV, ZC, WL, mean/variance, EMG feature sets.
from scipy.signal import spectrogram
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

# need to calculate metrics now

#relative muscle strength, time to muscle fatigue, activation timing, muscle-cocontraction 

# edit this to find the first contraction without a base # of samples
def first_contraction_indices(rms, baseline_samples=200, threshold_factor=2):
    """
    Find the start and end indices of the first contraction in an RMS array.

    Parameters:
    - rms: numpy array of RMS values
    - baseline_samples: number of initial samples to compute baseline
    - threshold_factor: multiplier of baseline std to set threshold

    Returns:
    - start_idx, end_idx: indices of the first contraction (None, None if none found)
    """
    # Compute baseline RMS from first few samples
    baseline_mean = np.mean(rms[:baseline_samples])
    baseline_std = np.std(rms[:baseline_samples])
    
    # Set threshold
    threshold = baseline_mean + threshold_factor * baseline_std
    
    # Boolean mask for above-threshold
    above_thresh = rms > threshold
    
    # Find first contraction
    in_contraction = False
    start_idx, end_idx = None, None
    for i, val in enumerate(above_thresh):
        if val and not in_contraction:
            start_idx = i
            in_contraction = True
        elif not val and in_contraction:
            end_idx = i
            break  # only want the first contraction
    
    # Handle case if contraction goes till the end
    if in_contraction and end_idx is None:
        end_idx = len(rms) - 1
    
    return start_idx, end_idx

def calculate_baseline(data):
    start_i, end_i = first_contraction_indices(data, baseline_samples=3, threshold_factor=1.5)
    baseline = np.mean(data[start_i:end_i]) if start_i is not None and end_i is not None else np.mean(data[:200])
    return baseline
    
# monitor changes in RMS (increases as fatigue progresses due to increased motor unit recruitment approx. ~20-30% increase compared to baseline)
# calculate median (MF) or mean frequency (MNF) (decreases as fatigue progresses due to slowing of muscle fiber conduction velocity)
# rate of change in RMS (increased by 31.7% in non-atheletes during fatigue) and MF (-0.89 Hz/sec decline in MF during fatigue)
def time_to_fatigue_post(rec_data, notch_data, fs, rms_threshold, mf_threshold):
    # RMS array calculation
    window_size = 200
    rms = np.sqrt(np.convolve(rec_data**2, np.ones(window_size)/window_size, mode='valid'))
    t_rms = np.arange(len(rms)) / fs  # time vector for rms
    
    # Determine baseline contraction rms
    baseline_rms = calculate_baseline(rms)
    
    #RMS rate of change
    rms_threshold_value = baseline_rms * 1/rms_threshold
    drms = np.gradient(rms, 1/fs) 
    rms_indices = np.where(drms > rms_threshold_value)
    # Handle empty array case
    if len(rms_indices) > 0:
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
def activation_timing_post(rms, fs, baseline_threshold): 
    """
    Return time points (seconds) where RMS magnitude exceeds `baseline_threshold`.

    Parameters
    - rms: array-like of RMS values (1D or 2D). If multi-dimensional, it will be flattened.
    - fs: sampling frequency in Hz
    - baseline_threshold: scalar threshold to compare RMS against

    Returns
    - numpy.ndarray of times (seconds) where rms > baseline_threshold. May be empty.
    """
    # Ensure a 1-D numpy array
    rms_arr = np.ravel(np.asarray(rms))
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

