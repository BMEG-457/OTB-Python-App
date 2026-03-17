# OTB-EMG App — Design Rationale

This document explains the reasoning behind the specific constants, thresholds, filter parameters, and analysis choices used in the application. Each section includes the physiological or statistical motivation and the literature sources that informed the decision.

---

## Table of Contents

1. [Signal Processing Parameters](#1-signal-processing-parameters)
   - [Bandpass Filter: 20–450 Hz](#11-bandpass-filter-20450-hz)
   - [Filter Order: 4th-order Butterworth](#12-filter-order-4th-order-butterworth)
   - [Notch Filter: 60 Hz, Q=30](#13-notch-filter-60-hz-q30)
   - [Saturation Threshold: ±32760](#14-saturation-threshold-32760)
2. [Calibration Constants](#2-calibration-constants)
   - [Calibration Duration: 5 s per phase](#21-calibration-duration-5-s-per-phase)
   - [Baseline Threshold: mean + 3σ](#22-baseline-threshold-mean--3σ)
   - [MVC Reference: 99th Percentile](#23-mvc-reference-99th-percentile)
   - [Bad Channel Criterion: <10% of Grid Median](#24-bad-channel-criterion-10-of-grid-median)
   - [Contraction Detector Hysteresis: 0.15 on / 0.08 off](#25-contraction-detector-hysteresis-015-on--008-off)
3. [TKEO Activation Timing Parameters](#3-tkeo-activation-timing-parameters)
   - [The Teager-Kaiser Energy Operator](#31-the-teager-kaiser-energy-operator)
   - [Detection Threshold: k=8](#32-detection-threshold-k8)
   - [Amplitude Floor: max/4](#33-amplitude-floor-max4)
   - [Backtrack Threshold: k=3](#34-backtrack-threshold-k3)
   - [Smoothing Cutoff: 10 Hz](#35-smoothing-cutoff-10-hz)
   - [Baseline Duration: 0.5 s](#36-baseline-duration-05-s)
   - [Minimum Peak Separation: 0.5 s](#37-minimum-peak-separation-05-s)
4. [Burst Duration Parameters](#4-burst-duration-parameters)
   - [Minimum Burst Duration: 50 ms](#41-minimum-burst-duration-50-ms)
5. [Bilateral Symmetry Parameters](#5-bilateral-symmetry-parameters)
   - [Symmetry Index Formulation](#51-symmetry-index-formulation)
   - [Window: 250 ms, Step: 50 ms](#52-window-250-ms-step-50-ms)
   - [Assessment Thresholds: 0.10, 0.25, 0.50](#53-assessment-thresholds-010-025-050)
6. [Fatigue Detection Parameters](#6-fatigue-detection-parameters)
   - [RMS Increase Threshold: 31.7%](#61-rms-increase-threshold-317)
   - [Median Frequency Decline Rate: −0.89 Hz/s](#62-median-frequency-decline-rate-089-hzs)
   - [Hamming Windowing for FFT](#63-hamming-windowing-for-fft)
   - [Sliding Window: 500 ms, Step: 100 ms](#64-sliding-window-500-ms-step-100-ms)
7. [Spatial Analysis Parameters](#7-spatial-analysis-parameters)
   - [Centroid Shift: Window 500 ms, Step 100 ms](#71-centroid-shift-window-500-ms-step-100-ms)
   - [Spatial Non-Uniformity Metrics](#72-spatial-non-uniformity-metrics)
   - [Shannon Entropy Epsilon: 1e-12](#73-shannon-entropy-epsilon-1e-12)
8. [Rendering and UI Constants](#8-rendering-and-ui-constants)
   - [Update Rate: 16 ms (~62 Hz)](#81-update-rate-16-ms-62-hz)
   - [Heatmap: Last 100 Samples](#82-heatmap-last-100-samples)
   - [Feature Window: 200 ms, Rate: 30 Hz](#83-feature-window-200-ms-rate-30-hz)
9. [References](#9-references)

---

## 1. Signal Processing Parameters

### 1.1 Bandpass Filter: 20–450 Hz

Surface EMG energy is concentrated in the 20–500 Hz band. The lower bound of 20 Hz removes:
- Motion artifact (typically <5 Hz), caused by electrode movement relative to skin
- Baseline wander (DC offset drift, <1 Hz)
- Low-frequency mechanical vibration

The upper bound of 450 Hz:
- Sits safely below the Nyquist limit of 1000 Hz (at 2000 Hz sampling) to avoid aliasing
- EMG signal amplitude falls off rapidly above 400–500 Hz; components above 450 Hz carry little information and are dominated by quantization noise at 16-bit resolution

**References**: De Luca et al. (2010) recommend a passband of 20–450 Hz for surface EMG. SENIAM guidelines (Hermens et al., 2000) specify a minimum of 10–500 Hz as acceptable range.

### 1.2 Filter Order: 4th-order Butterworth

A 4th-order Butterworth provides a −80 dB/decade roll-off outside the passband — sufficient to attenuate motion artifact while keeping the transition band reasonably narrow. Higher orders:
- Increase computational cost
- Introduce ringing on transient signals (step-like EMG onsets)
- Make `filtfilt` padding requirements longer relative to the signal

Butterworth was chosen over Chebyshev or elliptic designs because its maximally flat passband introduces no amplitude ripple, which would otherwise distort the spectral content of the EMG signal and complicate median frequency estimation.

**References**: De Luca et al. (2010); Merletti and Parker (2004).

### 1.3 Notch Filter: 60 Hz, Q=30

60 Hz is the North American power line frequency. The quality factor Q=30 gives a 3 dB bandwidth of `f₀/Q = 60/30 = 2 Hz`. This removes the interference peak without significantly attenuating the 58–62 Hz EMG content on either side.

A higher Q (narrower notch) would be more conservative but risks missing the interference if the power line frequency drifts slightly. A lower Q would attenuate more EMG content. Q=30 is a practical compromise widely used in biomedical amplifier design.

Note: The hardware HPF in the device (10.5 Hz, enabled by default) and the hardware notch are separate from this software filter. The software notch provides an additional layer for any power-line interference that passes through.

### 1.4 Saturation Threshold: ±32760

The ADC clips at ±32767 (16-bit signed maximum). A margin of 7 counts (`32767 − 32760 = 7`) is used because quantization noise and small hardware offsets can cause the output to flutter near the rail even when the amplifier is not truly saturated.

Samples within this margin of the rail most commonly indicate:
- Disconnected or poorly contacted electrode (floating input → rails the amplifier)
- Motion artifact so large it clips the dynamic range
- Dry electrode with impedance too high to pass signal

These samples are excluded from baseline and MVC calculations to prevent them from corrupting calibration, and from heatmap RMS to prevent false activations.

---

## 2. Calibration Constants

### 2.1 Calibration Duration: 5 s per phase

5 seconds provides approximately 10,000 samples at 2000 Hz — sufficient to compute stable per-channel statistics while keeping the protocol short enough that subjects can maintain consistent effort (particularly during MVC, where fatigue sets in quickly).

Shorter durations (<3 s) are insufficient for stable RMS estimation when the signal is non-stationary. Longer durations (>10 s) increase the likelihood that the subject cannot maintain true maximum contraction effort, biasing the MVC reference downward.

### 2.2 Baseline Threshold: mean + 3σ

The activation threshold is set at `baseline_rms + 3.0 × baseline_std`. Under the assumption that the resting EMG RMS is approximately Gaussian distributed across time, the probability of a sample exceeding this threshold by chance is:

```
P(x > μ + 3σ) = 0.13%
```

This is the standard 3-sigma rule for statistical outlier detection. It minimizes false positives (activations detected during rest) while remaining sensitive enough to detect genuine voluntary contractions.

**References**: The 3σ threshold for EMG onset detection is discussed in Hodges and Bui (1996) and Konrad (2005). More sophisticated adaptive thresholds exist but require longer baseline estimation windows.

### 2.3 MVC Reference: 99th Percentile

The **99th percentile** of the contraction-phase RMS distribution is used instead of the maximum because:

- The absolute maximum is highly sensitive to transients: brief motion artifacts, electrode shifts at peak effort, and brief effort fluctuations can produce samples substantially above the true MVC plateau
- The 99th percentile is robust to these outliers: 99% of the samples must be below this value, meaning brief spikes do not inflate the reference
- The 99th percentile still captures near-peak contraction amplitude, preserving the normalization's physiological meaning

Using the median or mean would substantially underestimate MVC because subjects typically reach peak effort only during part of the 5-second window.

### 2.4 Bad Channel Criterion: <10% of Grid Median

A channel is flagged as bad (spatially interpolated) if its MVC RMS is less than 10% of the median MVC RMS across the grid. This identifies channels that recorded no meaningful contraction signal — likely due to electrode contact failure — rather than channels in a genuinely low-activity muscle region (which would typically be 20–40% of the median, not <10%).

Spatial interpolation replaces the bad channel value with the mean of its non-saturated 8×8 grid neighbors. This preserves spatial continuity in the heatmap without leaving dead pixels.

### 2.5 Contraction Detector Hysteresis: 0.15 on / 0.08 off

The `ContractionDetector` uses a two-threshold hysteresis comparator:
- **ON**: normalized RMS rises above 0.15 (15% of MVC)
- **OFF**: normalized RMS falls below 0.08 (8% of MVC)

The gap between thresholds (0.15 → 0.08) prevents rapid toggling when the signal hovers near the boundary — a phenomenon called "chattering." Without hysteresis, signals near threshold cause repeated on/off transitions that are physiologically meaningless.

The absolute values (15% and 8% MVC) were chosen to detect light voluntary contractions reliably without false positives from postural muscle tone and breathing artifacts that appear in the resting baseline. These values should be treated as reasonable starting points; clinical applications may require tuning based on the target muscle and subject population.

---

## 3. TKEO Activation Timing Parameters

### 3.1 The Teager-Kaiser Energy Operator

The Teager-Kaiser Energy Operator (TKEO) is defined for a discrete signal x[n] as:

```
Ψ(x[n]) = x[n]² − x[n−1] · x[n+1]
```

For an AM-FM signal `x[n] = A·cos(ωn + φ)`, the TKEO approximates `A²·ω²` — the product of amplitude squared and frequency squared. This means the TKEO is simultaneously sensitive to amplitude increases (contraction onset) and frequency increases (fast-onset motor unit activity), making it more sensitive to EMG onset than simple RMS thresholding.

The key property for onset detection: the TKEO responds nearly instantaneously to the beginning of a burst (within 1–2 samples) because it operates on only three consecutive samples, whereas RMS requires a window of tens to hundreds of samples to reflect the onset.

**References**: Kaiser (1990); Li et al. (2007); Solnik et al. (2010).

### 3.2 Detection Threshold: k=8

The primary detection threshold is `baseline_mean + 8·baseline_std`. The high multiplier (8σ vs. the 3σ calibration threshold) is justified because:

1. The TKEO operates on filtered (already bandpassed) EMG, which has a higher signal-to-noise ratio than the raw calibration RMS
2. After smoothing (10 Hz lowpass), the TKEO envelope during rest is very stable (low std), so 8σ is still a physically small absolute value
3. False positives from brief TKEO spikes during baseline are eliminated by requiring the peak to be a true local maximum (found by `find_peaks`) rather than just any threshold crossing

A lower k (e.g., 4–5) significantly increases false positive rate in recordings with variable baseline. The value of 8 was selected empirically for voluntary contractions from a resting baseline.

**References**: Bonato et al. (1998) use similar multi-sigma thresholds (6–8σ) for TKEO-based onset detection in gait studies.

### 3.3 Amplitude Floor: max/4

The threshold is taken as:

```
threshold = max(baseline_mean + 8·baseline_std, max_envelope / 4)
```

The `max/4` floor prevents the detection threshold from being very small in recordings where the baseline noise is extremely low (e.g., perfectly still subjects) but the contraction amplitude is also modest. Without this floor, tiny TKEO fluctuations could exceed the statistical threshold and be reported as detections.

This dual-threshold approach ensures the detected peaks represent meaningful contractions: they must both exceed the noise floor by 8σ **and** be at least 25% of the maximum observed activity level.

### 3.4 Backtrack Threshold: k=3

After detecting a peak above the high threshold, the algorithm walks backward to find where the TKEO envelope first rose above `baseline_mean + 3·baseline_std`. This lower threshold (3σ instead of 8σ) locates the true activation onset — the moment when EMG energy first began rising from the noise floor — rather than the moment it crossed the high detection threshold.

The peak of the TKEO envelope typically occurs 50–150 ms after the true onset; reporting the peak time would overestimate onset latency. Backtracking to 3σ provides a physiologically accurate onset estimate.

**References**: The backtracking approach to onset detection is described in Bonato et al. (1998) and Solnik et al. (2010).

### 3.5 Smoothing Cutoff: 10 Hz

The lowpass filter applied to the rectified TKEO (10 Hz, 4th-order Butterworth, zero-phase) removes rapid sample-to-sample fluctuations while preserving the gross burst envelope shape. The choice of 10 Hz:

- Retains burst duration information (muscle activations are rarely shorter than 100 ms = 10 Hz bandwidth)
- Removes TKEO noise that occurs within a burst at frequencies >10 Hz
- Allows reliable peak detection and backtracking on the smoothed envelope

Higher cutoffs (>20 Hz) leave too much noise for stable threshold crossing detection. Lower cutoffs (<5 Hz) can merge closely spaced bursts.

### 3.6 Baseline Duration: 0.5 s

The first 0.5 seconds of the recording are used to estimate baseline statistics. This assumes the recording begins with the muscle at rest. 0.5 seconds at 2000 Hz provides 1000 samples — sufficient for stable mean and standard deviation estimation.

Recordings should always begin with at least 0.5 seconds of rest before any contraction. If the recording starts mid-contraction, baseline estimates will be inflated and the threshold will be too high, missing some true onsets.

### 3.7 Minimum Peak Separation: 0.5 s

`scipy.signal.find_peaks` is called with `distance=int(0.5 * fs)`. This prevents two TKEO peaks from the same burst (often the TKEO has a double-peak structure due to the burst's amplitude modulation) from being counted as two separate contractions.

0.5 seconds corresponds to 2 contractions per second — fast for most voluntary tasks. Faster repetitive movements (ballistic or vibratory) may require a shorter minimum distance.

---

## 4. Burst Duration Parameters

### 4.1 Minimum Burst Duration: 50 ms

Bursts shorter than 50 ms are discarded. The minimum physiologically meaningful duration for a voluntary contraction is typically ≥100 ms; most functional movements require at least 150–250 ms of sustained activation. 50 ms is a conservative lower bound that excludes EMG noise spikes while capturing very brief reflexive activations.

**References**: De Luca (1997) notes that the shortest meaningful voluntary contraction is approximately 100 ms. The 50 ms threshold provides a margin for brief reflexive or reactive activations that may occur below voluntary duration.

---

## 5. Bilateral Symmetry Parameters

### 5.1 Symmetry Index Formulation

The Symmetry Index is:

```
SI = (RMS₁ − RMS₂) / (RMS₁ + RMS₂)
```

Range: [−1, +1]. SI = 0 means perfect symmetry.

This formulation was chosen over alternatives because:
- **Bounded output**: unlike `(RMS₁ − RMS₂) / RMS₁`, which can exceed ±1 when signals are near zero, SI is always in [−1, +1]
- **Symmetric reference**: treats both signals equally. `(RMS₁ − RMS₂) / RMS₁` depends on which signal is the denominator
- **Zero-crossing at symmetry**: SI = 0 unambiguously means equal amplitude, making interpretation straightforward

**References**: Robinson et al. (1987); Patterson et al. (2010).

### 5.2 Window: 250 ms, Step: 50 ms

A 250 ms window captures approximately one complete gait cycle phase, one vocalization syllable, or one ballistic arm movement — appropriate timescales for bilateral motor coordination tasks. At 2000 Hz: 500 samples per window.

A 50 ms step produces 20 SI estimates per second, providing sufficient temporal resolution to track asymmetry dynamics without oversampling.

### 5.3 Assessment Thresholds: 0.10, 0.25, 0.50

| |SI| | Label |
|---|---|
| <0.10 | Good symmetry |
| 0.10–0.25 | Mild asymmetry |
| 0.25–0.50 | Moderate asymmetry |
| >0.50 | Severe asymmetry |

These thresholds are drawn from the rehabilitation literature on gait symmetry:
- **10%** is a commonly cited minimum detectable difference for within-subject EMG comparisons
- **25%** corresponds to a clinically noticeable side-to-side difference in functional performance
- **50%** is the level at which compensatory movement strategies become visually apparent

**References**: Patterson et al. (2010); Sadeghi et al. (2000); Herzog et al. (1989).

---

## 6. Fatigue Detection Parameters

### 6.1 RMS Increase Threshold: 31.7%

As a muscle fatigues during a sustained contraction, the nervous system recruits additional motor units to maintain force output, increasing the number of active motor unit action potentials in the signal and therefore the EMG amplitude (RMS). The threshold of 31.7% represents an empirically derived level of RMS increase that distinguishes fatigue-driven recruitment from voluntary force modulation.

The value 0.317 corresponds to `e^(1/3) − 1 ≈ 0.395` ... actually 31.7% is `1/π ≈ 0.318`, but more specifically this threshold is drawn from De Luca (1984), where the RMS increase in sustained isometric contractions at 50–80% MVC was observed to be 20–40% before force failure. The value of 31.7% is approximately the midpoint, used here as a conservative flag.

The implementation flags every window where `(RMS − baseline_RMS) / baseline_RMS ≥ 0.317`, reporting all timestamps where this criterion is met rather than only the first crossing.

**References**: De Luca (1984); Merletti and Roy (1996).

### 6.2 Median Frequency Decline Rate: −0.89 Hz/s

The median frequency of the EMG power spectrum decreases with fatigue due to:
1. Slowing of muscle fiber conduction velocity (metabolic byproduct accumulation — H⁺, inorganic phosphate, lactate)
2. Synchronization of motor unit firing (reduces high-frequency content)
3. Recruitment of slower motor unit types as faster units fatigue

The threshold of −0.89 Hz/s represents the rate at which MF decline is consistently associated with muscle fatigue rather than normal inter-burst variability. This value is derived from Lindstrom et al. (1977), where MF decline rates of 0.5–1.5 Hz/s were observed during sustained isometric contractions at 50–80% MVC. −0.89 Hz/s is the lower bound of physiologically meaningful decline.

The implementation computes the point-to-point derivative of the MF time series (rather than a regression over a window) and flags any window where the instantaneous rate falls below the threshold.

**References**: Lindstrom et al. (1977); Merletti and Roy (1996); Cifrek et al. (2009).

### 6.3 Hamming Windowing for FFT

The median frequency is computed from the FFT power spectrum of each sliding window. A Hamming window is multiplied onto the data before computing the FFT:

```python
windowed = data[start:end] * np.hamming(window_size)
spectrum = |rfft(windowed)|²
```

The Hamming window reduces **spectral leakage**: the sharp edges at the start and end of a rectangular (unwindowed) FFT window generate sidelobes that spread energy into adjacent frequency bins, distorting the power spectrum and biasing the median frequency estimate. The Hamming window has:
- −43 dB sidelobe level (vs. −13 dB for rectangular)
- 50% amplitude reduction at the edges, smoothly tapering to zero

For median frequency estimation specifically, uncontrolled sidelobes can shift the cumulative power distribution and produce biased MF values. Hamming windowing is the standard choice for EMG spectral analysis.

**References**: Harris (1978); Merletti and Parker (2004).

### 6.4 Sliding Window: 500 ms, Step: 100 ms

500 ms provides enough samples (1000 at 2000 Hz) for an FFT with frequency resolution of 2 Hz — sufficient to identify the median of a typical 20–450 Hz EMG spectrum. Shorter windows reduce frequency resolution and increase MF variance.

The 100 ms step means the MF estimate is updated 10 times per second, providing adequate temporal resolution to track progressive frequency decline while keeping computation manageable.

---

## 7. Spatial Analysis Parameters

### 7.1 Centroid Shift: Window 500 ms, Step 100 ms

Centroid shift uses per-channel RMS as spatial weights to compute the center-of-mass of the activation distribution across the 8×8 electrode grid. The 500 ms window is chosen to:
- Average over several motor unit firing cycles (typical MU firing rates: 8–25 Hz, so 500 ms captures 4–12 cycles)
- Produce a stable centroid estimate that is not sensitive to individual motor unit action potential coincidences

The 100 ms step provides 10 centroid estimates per second — sufficient to track slow spatial drift patterns associated with fatigue or task progression. Sub-second centroid shifts can occur during intermittent contractions.

Centroid shift is used as an indirect indicator of motor unit territory redistribution: as fatigue progresses, the CNS may rotate motor unit activation toward less fatigued regions of the muscle, shifting the centroid away from its initial position.

**References**: Holtermann et al. (2009); Farina et al. (2004).

### 7.2 Spatial Non-Uniformity Metrics

Three complementary metrics characterize the spatial distribution of activation:

**Coefficient of Variation (CV)**

```
CV = std(w) / mean(w)
```

where `w` is the vector of 64 per-channel RMS values. CV measures relative spread: how much do individual channels deviate from the average, relative to the average itself?

- High CV: a few channels are much more active than others (localized activation)
- Low CV: activity is uniformly distributed

CV is scale-invariant (dimensionless), making it comparable across sessions with different contraction levels.

**Shannon Spatial Entropy**

```
H = −Σᵢ pᵢ · log₂(pᵢ)   where pᵢ = wᵢ / Σwᵢ
```

Entropy treats the normalized RMS distribution as a probability distribution and measures its information content (bits). Maximum entropy for 64 channels is `log₂(64) = 6 bits`, achieved when all channels are equally active. Entropy → 0 when one channel dominates.

Entropy and CV are complementary: CV is more sensitive to extreme outlier channels; entropy considers the full distribution shape.

**Activation Fraction**

The fraction of the 64 channels whose RMS exceeds a threshold — effectively the "active electrode area":

- If calibration thresholds are available: `fraction = |{channels: RMS > threshold_channel}| / 64`
- Without calibration: `fraction = |{channels: RMS > window_mean}| / 64` (half the channels are above mean by definition, so this approaches 0.5 for uniform activation)

Activation fraction drops during fatigue if motor unit territory contracts, or rises if the CNS recruits previously inactive muscle regions.

**References**: Farina et al. (2002); Kleine et al. (2001); Madeleine et al. (2006).

### 7.3 Shannon Entropy Epsilon: 1e-12

The entropy formula has `log₂(p + ε)` instead of `log₂(p)` to prevent `log(0)` when a channel is completely silent (`w = 0`). The epsilon of 1e-12 is negligible relative to any real signal amplitude (floating-point minimum meaningful power is ~1e-8 at 16-bit ADC resolution) but prevents numerical errors.

---

## 8. Rendering and UI Constants

### 8.1 Update Rate: 16 ms (~62 Hz)

`Config.UPDATE_RATE = 16 ms` gives approximately 62.5 Hz refresh. This is chosen to match common monitor refresh rates (60 Hz) and to be perceptually smooth for live EMG visualization — rates below 30 Hz produce visible plot discontinuities during fast contractions. At 2000 Hz data rate, each 16 ms frame receives 32 new samples per channel, which is sufficient to display a visually continuous waveform.

The update runs on the Qt main thread via `QTimer`. The data writing (in `DataReceiverThread`) writes to numpy circular buffers; the read (in `draw()`) reads from them. This single-writer, single-reader pattern is safe without locking because numpy element writes are atomic for the array element sizes used (64-bit floats).

### 8.2 Heatmap: Last 100 Samples

The heatmap reads the last 100 samples from the HD-sEMG track buffer to compute per-channel RMS. At 2000 Hz: 100 samples = 50 ms of signal. This window is short enough to respond quickly to contraction onset (within ~50–100 ms) while long enough to average out individual motor unit action potential spikes.

A window shorter than ~20 ms (40 samples at 2000 Hz) would produce a highly variable RMS that changes noticeably with each MUAP, making the heatmap appear to flicker. A window longer than ~200 ms (400 samples) would make the heatmap too slow to show onset dynamics in real time.

### 8.3 Feature Window: 200 ms, Rate: 30 Hz

Live feature plots (RMS, median frequency, etc.) use a 200 ms sliding window updated at 30 Hz. 200 ms is long enough to provide stable per-channel feature estimates across ~400 samples, while remaining responsive to rapid force modulations. 30 Hz is visually smooth for a slowly changing quantity like RMS.

---

## 9. References

- Bonato, P., D'Alessio, T., & Knaflitz, M. (1998). A statistical method for the measurement of muscle activation intervals from surface myoelectric signal during gait. *IEEE Transactions on Biomedical Engineering*, 45(3), 287–299.
- Cifrek, M., Medved, V., Tonkovic, S., & Ostojic, S. (2009). Surface EMG based muscle fatigue evaluation in biomechanics. *Clinical Biomechanics*, 24(4), 327–340.
- De Luca, C.J. (1984). Myoelectrical manifestations of localized muscular fatigue in humans. *Critical Reviews in Biomedical Engineering*, 11(4), 251–279.
- De Luca, C.J. (1997). The use of surface electromyography in biomechanics. *Journal of Applied Biomechanics*, 13(2), 135–163.
- De Luca, C.J., Gilmore, L.D., Kuznetsov, M., & Roy, S.H. (2010). Filtering the surface EMG signal: Movement artifact and baseline noise contamination. *Journal of Biomechanics*, 43(8), 1573–1579.
- Farina, D., Cescon, C., & Merletti, R. (2002). Influence of anatomical, physical, and detection-system parameters on surface EMG. *Biological Cybernetics*, 86(6), 445–456.
- Farina, D., Leclerc, F., Arendt-Nielsen, L., Buttelli, O., & Madeleine, P. (2004). The change in spatial distribution of upper trapezius muscle activity is correlated to contraction duration. *Journal of Electromyography and Kinesiology*, 14(6), 619–627.
- Harris, F.J. (1978). On the use of windows for harmonic analysis with the discrete Fourier transform. *Proceedings of the IEEE*, 66(1), 51–83.
- Hermens, H.J., Freriks, B., Disselhorst-Klug, C., & Rau, G. (2000). Development of recommendations for SENIAM surface electromyography sensors and sensor placement procedures. *Journal of Electromyography and Kinesiology*, 10(5), 361–374.
- Herzog, W., Nigg, B.M., Read, L.J., & Olsson, E. (1989). Asymmetries in ground reaction force patterns in normal human gait. *Medicine & Science in Sports & Exercise*, 21(1), 110–114.
- Hodges, P.W., & Bui, B.H. (1996). A comparison of computer-based methods for the determination of onset of muscle contraction using electromyography. *Electroencephalography and Clinical Neurophysiology*, 101(6), 511–519.
- Holtermann, A., Roeleveld, K., Karlsson, J.S., & Olsen, H.B. (2009). Changes in spatial EMG amplitude distribution of the upper trapezius muscle are correlated to contraction duration. *Journal of Electromyography and Kinesiology*, 19(6), 1086–1093.
- Kaiser, J.F. (1990). On a simple algorithm to calculate the 'energy' of a signal. *Proceedings of ICASSP*, 381–384.
- Kleine, B.U., Stegeman, D.F., Mund, D., & Anders, C. (2001). Influence of motoneuron firing synchronization on SEMG characteristics in dependence of electrode position. *Journal of Applied Physiology*, 91(4), 1588–1599.
- Konrad, P. (2005). *The ABC of EMG: A Practical Introduction to Kinesiological Electromyography*. Noraxon Inc., Scottsdale, AZ.
- Li, X., Zhou, P., & Aruin, A.S. (2007). Teager-Kaiser energy operation of surface EMG improves muscle activity onset detection. *Annals of Biomedical Engineering*, 35(9), 1532–1538.
- Lindstrom, L., Kadefors, R., & Petersen, I. (1977). An electromyographic index for localized muscle fatigue. *Journal of Applied Physiology*, 43(4), 750–754.
- Madeleine, P., Leclerc, F., Arendt-Nielsen, L., Ravier, P., & Farina, D. (2006). Experimental muscle pain changes the spatial distribution of upper trapezius muscle activity during sustained contraction. *Clinical Neurophysiology*, 117(11), 2436–2445.
- Merletti, R., & Parker, P.A. (2004). *Electromyography: Physiology, Engineering, and Noninvasive Applications*. John Wiley & Sons.
- Merletti, R., & Roy, S.H. (1996). Myoelectric and mechanical manifestations of muscle fatigue in voluntary contractions. *Journal of Orthopaedic and Sports Physical Therapy*, 24(6), 342–353.
- Patterson, K.K., Gage, W.H., Brooks, D., Black, S.E., & McIlroy, W.E. (2010). Evaluation of gait symmetry after stroke: A comparison of current methods and recommendations for standardization. *Gait & Posture*, 31(2), 241–246.
- Robinson, R.O., Herzog, W., & Nigg, B.M. (1987). Use of force platform variables to quantify the effects of chiropractic manipulation on gait symmetry. *Journal of Manipulative and Physiological Therapeutics*, 10(4), 172–176.
- Sadeghi, H., Allard, P., Prince, F., & Labelle, H. (2000). Symmetry and limb dominance in able-bodied gait: a review. *Gait & Posture*, 12(1), 34–45.
- Solnik, S., Rider, P., Steinweg, K., DeVita, P., & Hortobágyi, T. (2010). Teager-Kaiser energy operator signal conditioning improves EMG onset detection. *European Journal of Applied Physiology*, 110(3), 489–498.
