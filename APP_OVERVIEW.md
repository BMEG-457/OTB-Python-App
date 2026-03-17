# OTB EMG Desktop Application — Detailed Architecture Overview

This document describes the Python desktop application in `BMEG 457 scripts/`. It is written for a reader with no prior context about the codebase, but assumes a general understanding of Python and basic signal processing concepts.

---

## Table of Contents

1. [What This Application Does](#1-what-this-application-does)
2. [The Hardware: Sessantaquattro+](#2-the-hardware-sessantaquattro)
3. [Project Structure](#3-project-structure)
4. [Application Modes and Entry Point](#4-application-modes-and-entry-point)
5. [Device Communication Protocol](#5-device-communication-protocol)
6. [Live Data Pipeline](#6-live-data-pipeline)
7. [Signal Processing](#7-signal-processing)
8. [Calibration](#8-calibration)
9. [Visualization](#9-visualization)
10. [Recording](#10-recording)
11. [Session Persistence](#11-session-persistence)
12. [Data Analysis Mode](#12-data-analysis-mode)
13. [Feature Extraction Algorithms](#13-feature-extraction-algorithms)
14. [UI Architecture](#14-ui-architecture)
15. [Dependency Rationale](#15-dependency-rationale)
16. [Glossary](#16-glossary)
17. [References](#17-references)

---

## 1. What This Application Does

This is a real-time electromyography (EMG) viewer and analysis tool built for the OTB Sessantaquattro+ high-density surface EMG (HD-sEMG) device. It has two independent operating modes:

- **Live Data Mode**: Streams 64-channel EMG data from the device over WiFi in real time, displays it, and optionally records it to a CSV file.
- **Data Analysis Mode**: Loads previously recorded CSV files and runs post-hoc feature extraction (activation timing, burst duration, bilateral symmetry, fatigue) with interactive visualization.

### What is EMG?

Electromyography measures the electrical activity produced by skeletal muscles when they contract. Surface EMG electrodes placed on the skin above a muscle pick up the combined electrical signal from many individual motor units (a motor unit is one motor neuron and all the muscle fibers it controls). The raw signal is a broadband noise-like waveform whose amplitude increases with contraction force and whose frequency content changes with muscle fatigue.

HD-sEMG uses an 8×8 grid of 64 electrodes to capture the spatial distribution of muscle activity across the skin surface, enabling visualization of motor unit territories and propagation patterns.

---

## 2. The Hardware: Sessantaquattro+

The Sessantaquattro+ (Italian: "sixty-four plus") is an OTB Bioelettronica wireless HD-sEMG amplifier. Relevant hardware parameters:

| Parameter | Value | Notes |
|---|---|---|
| Channels | Up to 64 EMG + 8 auxiliary | Configurable via NCH/MODE bits |
| Sampling rate | 500, 1000, 2000, or 4000 Hz | Configured at session start |
| ADC resolution | 16-bit signed | Range: −32768 to +32767 |
| Communication | TCP over WiFi | Device connects to laptop as TCP client |
| Port | 45454 | Hard-coded in device firmware |
| Byte order | Big-endian | Each sample = 2 bytes |

The **laptop connects to the device's WiFi hotspot**, and the **laptop acts as the TCP server**. The device connects to it as a TCP client, not the other way around. This is why `SessantaquattroPlus.start_server()` binds to `0.0.0.0:45454` and waits for an incoming connection.

---

## 3. Project Structure

```
BMEG 457 scripts/
├── main.py                        Entry point, window wiring, device init
└── app/
    ├── core/
    │   ├── config.py              App-wide constants (update rate, window size)
    │   ├── device.py              SessantaquattroPlus — TCP protocol & command encoding
    │   ├── track.py               Track — live plot with circular buffer
    │   └── analysis_track.py     AnalysisTrack — static post-hoc plot
    ├── data/
    │   ├── data_receiver.py      DataReceiverThread — background TCP reader
    │   └── csv_loader.py         CSVDataLoader — loads recorded CSV files
    ├── managers/
    │   ├── track_manager.py      Creates and manages live plot tracks
    │   ├── analysis_track_manager.py  Manages analysis-mode plot tracks
    │   ├── recording_manager.py  Writes data to CSV during recording
    │   ├── streaming_controller.py   Toggles streaming on/off
    │   └── time_navigation_controller.py  Scroll/zoom in analysis mode
    ├── processing/
    │   ├── filters.py            Bandpass, notch, and rectification filters
    │   ├── features.py           Post-hoc EMG feature extraction
    │   ├── pipeline.py           ProcessingPipeline registry
    │   └── transforms.py         FFT transform
    └── ui/
        ├── windows/
        │   ├── main_window.py    SoundtrackWindow — live data window
        │   └── data_analysis_window.py  DataAnalysisWindow
        ├── dialogs/
        │   └── dialogs.py        CalibrationDialog, channel/track selectors
        ├── tabs/
        │   ├── base_tab.py       Abstract BaseTab layout pattern
        │   └── tab_implementations.py  AllTracksTab, AccessoryTab, HeatmapTab
        └── panels/
            ├── data_viewing_panel.py  Signal processing controls (analysis mode)
            └── features_panel.py     Feature extraction buttons (analysis mode)
```

---

## 4. Application Modes and Entry Point

`main.py` is the sole entry point. It follows a **lazy initialization** pattern for the device connection: the device object (`SessantaquattroPlus`) is created immediately at startup, but the TCP socket is not opened until the user clicks Stream, Record, or Calibrate for the first time. This prevents connection errors at startup if the device is not yet powered on or the user wants to go directly to data analysis mode.

```
main()
├── Creates SessantaquattroPlus()      # No socket opened yet
├── Creates SelectionWindow            # Mode selector
├── Creates SoundtrackWindow(device)   # Live mode window (hidden)
├── Creates DataAnalysisWindow()       # Analysis mode window (hidden)
│
├── Wires SelectionWindow buttons -> show/hide appropriate window
│
└── Wires live window buttons to handlers in main.py:
    ├── handle_stream_toggle()
    ├── handle_record_toggle()
    └── handle_calibration()
          Each handler:
          ├── If receiver_thread is None (first use):
          │     device.create_command(FSAMP=2, NCH=3, MODE=0, ...)
          │     device.start_server()   <- Opens socket, waits for device
          │     device.send_command()   <- Sends 16-bit config word
          │     live_data_window.initialize_receiver()
          └── Then calls the actual action (toggle_streaming, etc.)
```

**Why are buttons wired in main.py, not inside SoundtrackWindow?** The window cannot open the TCP socket itself because it would need to call `sys.exit()` on connection failure, which is inappropriate for a widget. Keeping the device lifecycle in `main.py` separates concerns: the window manages visualization, `main.py` manages connectivity.

---

## 5. Device Communication Protocol

### Connection Sequence

1. Laptop opens TCP server on `0.0.0.0:45454` (listens for incoming connection)
2. User powers on device, then connects the laptop to the device's WiFi hotspot
3. Device connects to laptop as TCP client
4. Laptop sends a 2-byte configuration command
5. Device immediately begins streaming data

### Command Encoding

The configuration is packed into a single 16-bit signed integer transmitted as 2 bytes in big-endian order:

```
Bit  0     : GO    — 1 = start streaming, 0 = stop
Bit  1     : REC   — SD card recording (not used)
Bits 2–3   : TRIG  — trigger mode
Bits 4–5   : EXTEN — extension factor
Bit  6     : HPF   — hardware high-pass filter (0 = DC, 1 = 10.5 Hz hardware HPF)
Bit  7     : HRES  — resolution (0 = 16-bit, 1 = 24-bit)
Bits 8–10  : MODE  — working mode (0 = monopolar)
Bits 11–12 : NCH   — channel count selector
Bits 13–14 : FSAMP — sampling frequency selector
```

Default command used by this app: `FSAMP=2` (2000 Hz), `NCH=3` (72 channels in monopolar mode — 64 EMG + 8 auxiliary), `MODE=0` (monopolar), `HPF=1` (hardware HPF at 10.5 Hz enabled), `GO=1`.

### Packet Format

After the command is sent, the device streams continuously. Each packet contains one "tick" of data equal to `frequency / 16` samples per channel (at 2000 Hz: 125 samples per packet). Packet size in bytes: `nchannels × 2 × (frequency / 16)`.

At 2000 Hz with 72 channels: `72 × 2 × 125 = 18000 bytes` per packet. The device transmits 16 packets per second.

Data is packed as **big-endian 16-bit signed integers** in interleaved sample order: all channels for sample 0, all channels for sample 1, etc. After unpacking with `struct.unpack`, the array is reshaped to `(nchannels, n_samples)` — channels as rows, time as columns. This layout is used throughout the processing pipeline.

---

## 6. Live Data Pipeline

This describes the complete data path from hardware to screen:

```
Device (WiFi)
    │  TCP stream: 18000 bytes/packet at 16 packets/sec (2000 Hz, 72ch)
    ▼
DataReceiverThread  (background QThread, stays alive for entire session)
    │
    │  1. recv() accumulates bytes in a buffer
    │  2. When buffer >= expected_bytes, one complete packet is extracted
    │  3. struct.unpack() → numpy array (n_samples, nchannels)
    │  4. reshape → (nchannels, n_samples)
    │
    ├── stage_output.emit('raw', data)
    │
    ├── filtered = Pipeline('filtered').run(data)
    ├── stage_output.emit('filtered', filtered)
    │
    ├── rectified = Pipeline('rectified').run(filtered)
    ├── stage_output.emit('rectified', rectified)
    │
    ├── processed = Pipeline('final').run(data)     <- runs on raw data
    ├── stage_output.emit('final', processed)
    │
    └── if self.running:   ← controlled by StreamingController
          track.feed(processed)  for each Track

stage_output signal consumed by:
    ├── RecordingManager.on_data_for_recording  (filters to 'raw' stage only; writes when is_recording=True)
    └── CalibrationDialog.on_stage_output       (filters to 'filtered' stage only; only during calibration)

StreamingController
    ├── start_streaming() → sets receiver_thread.running = True, starts QTimer(16ms)
    └── stop_streaming()  → sets receiver_thread.running = False, stops QTimer

QTimer (16ms ≈ 62 fps)
    └── SoundtrackWindow.update_plot()
          ├── TrackManager.draw_all_tracks()  ← redraws pyqtgraph plots from buffers
          └── update_heatmap()               ← updates 8x8 heatmap display
```

### Why is the thread never restarted?

The `DataReceiverThread` is created once and runs in a blocking `socket.recv()` loop for the entire session. The `StreamingController` only sets `receiver_thread.running = True/False` to pause and resume data feeding — it does not restart the thread. This design avoids re-establishing the TCP socket and re-sending the configuration command on each pause/resume, which the device firmware may not support reliably.

The consequence: the thread always reads from the socket (consuming and discarding packets when `running=False`) to prevent the device's TCP send buffer from filling up and stalling the connection. A 5-second socket timeout prevents permanent blocking if the device disconnects.

### Pipeline Registry

`app/processing/pipeline.py` implements a module-level dictionary of named `ProcessingPipeline` objects. Each pipeline is a list of callables applied in sequence to a `(nchannels, n_samples)` numpy array. Configured pipelines:

| Name | Stages |
|---|---|
| `filtered` | butter_bandpass(20–450 Hz) → notch(60 Hz) |
| `rectified` | abs() |
| `final` | (empty — passthrough; reserved for future use) |
| `fft` | FFT transform |

The `final` pipeline intentionally runs on raw data (`reshaped_data`, not `filtered`) so that the "All Tracks" tab displays the unmodified EMG waveform. The filtered data is available from the `filtered` stage signal.

---

## 7. Signal Processing

### Bandpass Filter: 20–450 Hz

EMG signal energy is concentrated in the 20–500 Hz range. Below 20 Hz, motion artifact and low-frequency drift dominate. Above 450 Hz, signal amplitude falls off rapidly and aliasing risk increases as the signal approaches the Nyquist limit of 1000 Hz (at 2000 Hz sampling). A 4th-order Butterworth zero-phase filter (`scipy.signal.filtfilt`) is used.

**Why Butterworth?** It provides a maximally flat passband with no ripple, preserving the amplitude of EMG frequency components without periodic amplitude distortions that would complicate spectral analysis.

**Why zero-phase (filtfilt)?** Forward-only filtering introduces frequency-dependent phase delay, shifting events in time by amounts that vary across frequencies. `filtfilt` applies the filter forward then backward, canceling phase distortion. This is critical for accurate timing detection. The tradeoff is that `filtfilt` is non-causal — it requires the full signal — so it is used only in post-hoc analysis. For real-time visualization, phase delay from a causal filter is acceptable since live display is for monitoring, not precise timing measurement.

**References**: De Luca et al. (2010) recommend 20–450 Hz for surface EMG. SENIAM guidelines (Hermens et al., 2000) suggest a minimum passband of 10–500 Hz.

### Notch Filter: 60 Hz

North American power line frequency. A 2nd-order Butterworth bandstop filter centered at 60 Hz with quality factor Q=30 (bandwidth ≈ 2 Hz) removes power line interference without significantly distorting neighboring frequency content.

### Rectification

`abs(data)` converts the bipolar EMG to a positive-only signal. Full-wave rectification is the standard preprocessing step before envelope extraction (RMS or lowpass) because the mean of unrectified EMG is zero regardless of amplitude.

---

## 8. Calibration

Calibration establishes two reference values per channel from a live recording session: the **baseline RMS** (muscle at rest) and the **MVC RMS** (maximum voluntary contraction). These normalize heatmap values to the range [0, 1].

### Procedure

`CalibrationDialog` runs a two-phase timed protocol:

1. **Rest phase** (5 seconds): Subject relaxes completely. The dialog subscribes to the `filtered` stage signal and collects per-packet RMS values for each channel.

2. **Contraction phase** (5 seconds): Subject performs a maximum voluntary contraction. The same RMS collection runs.

### Threshold Computation

```
baseline_rms  = mean(rest_rms_samples, axis=time)       # per channel
baseline_std  = std(rest_rms_samples, axis=time)        # per channel
threshold     = baseline_rms + 3.0 * baseline_std
mvc_rms       = 99th_percentile(contraction_rms_samples, axis=time)  # per channel
```

The threshold of `mean + 3σ` is a standard statistical detection threshold: under a Gaussian model, values above this level occur with only 0.13% probability during rest, minimizing false positives.

The **99th percentile** of the contraction phase is used instead of the maximum because the true maximum may include noise transients (e.g., motion artifact at peak effort). The 99th percentile is robust to these outliers while still capturing near-maximum contraction amplitude.

### Saturation Handling

The ADC clips at ±32767. Samples within 7 counts of the rail (`|x| > 32760`) indicate a disconnected or poorly contacted electrode (which typically rails the amplifier input). Saturated samples are excluded before computing both rest baseline and MVC.

Channels where all contraction samples are saturated receive `mvc_rms = 0.0` and are corrected by **spatial interpolation**: the value is replaced with the mean of its non-saturated neighbors in the 8×8 electrode grid. Channels below 10% of the grid median MVC are also treated as bad and spatially interpolated.

### Heatmap Normalization

During live streaming, `update_heatmap()` reads the last 100 samples from the HD-sEMG track's circular buffer, computes per-channel RMS (excluding saturated samples), and normalizes:

```python
normalized_rms = current_rms[:64] / (mvc_rms[:64] + 1e-10)
normalized_rms = np.clip(normalized_rms, 0, 1)
```

The `1e-10` prevents division by zero. Values above 1.0 (contraction exceeding the MVC reference) are clipped to 1.0.

---

## 9. Visualization

### Live Track Plot (Track class)

Each `Track` is a pyqtgraph `PlotWidget` containing one `PlotDataItem` (curve) per channel. Data is stored in a **circular buffer** of shape `(nchannels, buffer_size)` where `buffer_size = int(fs * plot_time)`. On each `feed()` call, new samples are written into the buffer at the current write pointer with wraparound. On each `draw()` call, the buffer contents are read and plotted against a time axis.

A circular buffer is used because reallocating a new array on every packet would be wasteful. At 2000 Hz × 72 channels, the incoming data rate is 144,000 samples/second; the buffer must be updated efficiently without large memory allocations.

**Plot time selector**: The top-bar dropdown (100ms, 250ms, 500ms, 1s, 5s, 10s) changes how much of the buffer is shown in the plot window. Choosing a shorter window allows viewing fine temporal detail; longer windows reveal slower trends.

### Heatmap (HeatmapTab)

The heatmap tab displays an 8×8 pyqtgraph `ImageItem` with a viridis colormap, normalized to [0, 1]. Each pixel corresponds to one electrode channel. Channel-to-grid mapping:

```
channel_idx = col * 8 + (7 - row)
```

This places channel 0 at bottom-left, increasing upward within each column, then left-to-right across columns. This matches the physical orientation of the OTB 8×8 electrode array (bottom-left = electrode 1 in column-major order).

`ImageItem.setImage(data.T, levels=(0,1))` — the transpose is required because pyqtgraph uses (x=column, y=row) indexing, opposite to numpy's (row, column) convention.

### Update Rate

The `QTimer` fires every `Config.UPDATE_RATE = 16 ms`, yielding approximately 62.5 Hz refresh. All visualization runs on the Qt main (UI) thread. The background `DataReceiverThread` writes only to numpy buffers (which are not Qt objects), making the access thread-safe for this pattern: one writer, one reader, no locking needed because numpy array element writes are atomic for the sizes used here.

---

## 10. Recording

`RecordingManager` accumulates incoming data packets (connected to the `raw` stage signal) in memory and writes them to a timestamped CSV file when recording is stopped.

**Maximum recording length**: `max_samples=1_000_000` samples. An overflow signal triggers a warning dialog and stops recording automatically, preventing unbounded memory growth.

**File location**: Determined by `app/core/paths.py:get_data_dir()`, which returns a path adjacent to the executable (PyInstaller frozen build) or adjacent to the script root (development). This ensures recordings are never written inside the application package directory.

---

## 11. Session Persistence

After a successful calibration, `SoundtrackWindow.save_session_data()` writes the per-channel calibration arrays to `data/previous_session.csv`. On the next launch, `load_session_data()` reads this file and restores `baseline_rms`, `threshold`, and `mvc_rms` so the heatmap is immediately functional without recalibration.

The arrays are serialized as comma-separated floats within a single CSV cell (e.g., `"0.001234,0.002345,..."`) and parsed back on load. Calibration is saved immediately after the dialog completes and again on application exit.

**Critical initialization order**: `load_session_data()` is called inside `SoundtrackWindow.__init__()` before any widgets are created. All UI elements that depend on `self.is_calibrated` must be created after this call so they can read the correct initial state.

---

## 12. Data Analysis Mode

`DataAnalysisWindow` is completely independent of the live mode window. It requires no device connection and can be opened without the device present.

### Data Loading

`CSVDataLoader.load_file()` reads a recorded CSV, extracts channel data as a numpy array of shape `(nchannels, n_samples)`, and estimates the sample rate from the timestamp column. Timestamp handling:

1. **Duplicated timestamps**: If the CSV records one timestamp per packet (not per sample), timestamps are linearly interpolated to assign a unique timestamp to each sample.
2. **Non-monotonic timestamps**: Any non-increasing timestamp is discarded before the sample rate is estimated.

### Time Navigation

`TimeNavigationController` manages the current view window: a start time and a duration. The slider has 1000 steps (0.1% time resolution). Step buttons (`<` and `>`) move the window by 10% of its duration. The window duration is adjustable via a text input with a validator clamping to [0.1, 1000] seconds.

### Signal Processing Controls

The `DataViewingPanel` exposes:

- **Channel selector**: Up to 2 channels displayed simultaneously
- **Rectify**: Apply `abs()` before envelope extraction
- **Envelope type**: None, RMS (sliding window), or Lowpass (4th order Butterworth at 10 Hz, zero-phase)
- **RMS window**: Samples for sliding-window RMS (default 50 samples = 25 ms at 2000 Hz)
- **Lowpass cutoff**: Cutoff frequency for lowpass envelope (default 10 Hz)

---

## 13. Feature Extraction Algorithms

All functions in `app/processing/features.py` are post-hoc only (non-causal), using `scipy.signal.filtfilt` for zero-phase filtering. All functions share the same timestamp preprocessing pipeline:

1. Remove NaN samples
2. Interpolate duplicated timestamps
3. Enforce strictly increasing timestamps
4. Re-estimate sample rate from median inter-sample interval of the cleaned timestamps

### 13.1 TKEO Activation Timing

The **Teager-Kaiser Energy Operator (TKEO)** detects the onset of muscle activation. For a discrete signal x[n]:

```
Ψ(x[n]) = x[n]² − x[n−1] · x[n+1]
```

The TKEO amplifies amplitude-frequency products, making it more sensitive to EMG onset than simple RMS thresholding, which rises gradually [Kaiser, 1990; Solnik et al., 2010].

**Processing chain in `compute_tkeo_activation_timing()`**:

1. Bandpass filter: 20–450 Hz, 4th order Butterworth, zero-phase
2. Compute TKEO point-by-point
3. Rectify: `abs(tkeo)`
4. Smooth: 4th order Butterworth lowpass at 10 Hz, zero-phase — removes rapid TKEO fluctuations, producing a smooth energy envelope
5. Baseline: mean and std of the first 0.5 seconds of the smoothed envelope
6. Detection threshold: `max(baseline_mean + 8·baseline_std, max_envelope / 4)` — the two-threshold approach prevents false detections in low-amplitude signals where the statistical threshold alone would be very small
7. Find peaks above threshold with minimum separation of 0.5 s (`scipy.signal.find_peaks`)
8. **Backtrack** from each peak to find the true onset: walk backward until the envelope drops below `baseline_mean + 3·baseline_std`

**Why backtrack?** The peak of the TKEO envelope occurs well into the burst. Backtracking to a lower threshold finds where energy first began rising from baseline — the true activation onset [Bonato et al., 1998].

**Parameter rationale**:
- `k_threshold = 8`: High multiplier reduces false positives. Appropriate for voluntary contractions where onset is well above the noise floor.
- `backtrack_k = 3`: A lower threshold (3σ) finds the earlier onset crossing, providing a more precise timing estimate.
- `min_peak_distance_sec = 0.5 s`: Prevents double-counting a single burst's TKEO peak.
- `smooth_cutoff = 10 Hz`: Retains gross burst shape while removing point-to-point TKEO noise.

### 13.2 Burst Duration

`compute_burst_duration()` reuses the same TKEO pipeline but detects threshold crossings instead of peaks:

- **Onset**: first sample where the TKEO envelope rises above `baseline_mean + 3·baseline_std`
- **Offset**: first subsequent sample where the envelope falls back below that threshold

Only bursts whose peak TKEO value exceeds the higher detection threshold and whose duration exceeds 50 ms are counted. The 50 ms minimum prevents counting brief noise transients; the minimum physiologically meaningful voluntary contraction is typically ≥100 ms [De Luca, 1997].

Returns: burst count, mean duration ± standard deviation.

### 13.3 Bilateral Symmetry Index

The **Symmetry Index (SI)** quantifies relative difference in muscle activation between two signals (typically left vs. right limb):

```
SI = (RMS₁ − RMS₂) / (RMS₁ + RMS₂)
```

Range: [−1, +1]. A value of 0 means perfect symmetry. Positive values indicate signal 1 is dominant; negative values indicate signal 2 is dominant.

This formulation [Robinson et al., 1987] is preferred over the simple percentage difference `(RMS₁ − RMS₂) / RMS₁` because it is bounded and symmetric — it treats both signals as equally valid references.

**Implementation**: Aligns both signals to t=0, resamples both to the lower of the two sample rates, then computes a sliding-window RMS SI with 250 ms windows and 50 ms step (producing a time series). Summary statistics (mean SI, std SI, max asymmetry) are reported along with an assessment:

| |SI| | Assessment |
|---|---|
| < 0.10 | Good symmetry |
| 0.10–0.25 | Mild asymmetry |
| 0.25–0.50 | Moderate asymmetry |
| > 0.50 | Severe asymmetry |

### 13.4 Fatigue Detection

Two complementary fatigue indicators are tracked simultaneously [De Luca, 1984]:

**1. RMS increase** (`rms_threshold = 0.317`, i.e., 31.7%):
As a muscle fatigues during a sustained contraction, the central nervous system recruits additional motor units to maintain force output, increasing EMG amplitude. Fatigue is flagged when the sliding-window RMS (500 ms window, 100 ms step) exceeds the baseline RMS by 31.7% for at least 3 consecutive windows (300 ms sustained elevation), excluding the initial baseline period.

**2. Median frequency (MF) decline** (`mf_threshold = −0.89 Hz/s`):
As fatigue progresses, accumulation of metabolic byproducts (hydrogen ions, inorganic phosphate) reduces muscle fiber conduction velocity, compressing the EMG power spectrum toward lower frequencies [Lindstrom et al., 1977; Merletti & Roy, 1996]. The median frequency — the frequency that divides the power spectrum in half — declines measurably.

MF is computed per sliding window using an FFT with **Hamming windowing** (reduces spectral leakage from the window edges) via `scipy.fft.rfft`. Fatigue is flagged when a sliding linear regression over the last 10 MF windows (covering 1 second of MF history) produces a slope ≤ −0.89 Hz/s.

**Why regression instead of point-to-point derivative?** The MF signal is inherently noisy; point-to-point differences trigger frequent false positives from brief FFT transients at burst onset. Regression over 10 consecutive windows requires a sustained monotonic decline, not a single large negative step, making it substantially more robust.

---

## 14. UI Architecture

### Window Hierarchy

```
SelectionWindow          (400×300, startup screen)
├── → SoundtrackWindow  (1200×800, live data mode)
│       ├── Top control bar: Plot time, Calibrate, Stream, Record, Pause, Status
│       └── QTabWidget
│             ├── AllTracksTab     scrollable list of all EMG track plots
│             ├── AccessoryTab     AUX / quaternion / buffer tracks
│             └── HeatmapTab       8×8 normalized activation heatmap
└── → DataAnalysisWindow (1200×800, post-hoc analysis mode)
        ├── File controls row
        ├── Time navigation row (slider, step buttons, window input)
        └── QSplitter (vertical)
              ├── Top: shared plot area (left) + control tabs (right, 250px)
              │         ├── DataViewingPanel   (channel select, processing)
              │         └── FeaturesPanel      (TKEO, burst, symmetry, fatigue buttons)
              └── Bottom: Results text panel (monospace, dark theme)
```

### BaseTab Pattern

All live-mode tabs subclass `BaseTab` (`app/ui/tabs/base_tab.py`), which enforces a two-panel horizontal layout:

- **Content area** (left, ~75%): The primary visualization (plots or heatmap), inside a `QScrollArea`
- **Control panel** (right, ~25%): Buttons and controls specific to this tab

Subclasses must implement three methods:
- `create_content_area() -> QWidget`
- `create_control_panel() -> QWidget`
- `get_tab_name() -> str`

They may also override `connect_signals(window)` to wire their buttons to the parent window's methods. This is called during `SoundtrackWindow.__init__()` after all tabs are created.

**To add a new tab**: subclass `BaseTab`, implement the three required methods, and append an instance to `self.tab_list` in `SoundtrackWindow._create_tabs()`.

### Dialog Pattern

- `CalibrationDialog`: Modal; emits `calibration_complete(baseline_rms, threshold, mvc_rms)` as a Qt signal on success. Subscribes to `stage_output('filtered', ...)` during the collection phases, then disconnects.
- `ChannelSelectorDialog`: Grid of checkboxes for selecting which channels to display on a track.
- `TrackVisibilityDialog`: List of checkboxes for toggling entire tracks visible/invisible.

---

## 15. Dependency Rationale

| Library | Used for | Why |
|---|---|---|
| PyQt5 | UI framework, threading | Mature, cross-platform; `QThread` + `pyqtSignal` provide thread-safe UI communication |
| pyqtgraph | Real-time plot rendering | Significantly faster than matplotlib for continuously updated plots; uses OpenGL acceleration where available |
| numpy | All array operations | Vectorized operations; `np.ndarray` is the universal data type throughout the pipeline |
| scipy | Filter design, FFT, resampling, peak finding | Trusted, well-tested implementations of standard DSP algorithms |

---

## 16. Glossary

| Term | Definition |
|---|---|
| ADC | Analog-to-Digital Converter. Converts voltage to integer. 16-bit ADC: range −32768 to +32767. |
| Butterworth filter | A filter with a maximally flat (ripple-free) frequency response in the passband. |
| Circular buffer | A fixed-size array used as a ring: new data overwrites the oldest data when full. |
| filtfilt | Zero-phase filtering: apply filter forward then backward to cancel phase distortion. Non-causal; requires the full signal in advance. |
| HD-sEMG | High-density surface EMG. An array of many closely spaced electrodes that captures the spatial distribution of muscle activity. |
| MVC | Maximum Voluntary Contraction. The maximum force a subject can voluntarily produce; used as a normalization reference for %MVC amplitude. |
| Motor unit | One motor neuron and all the muscle fibers it innervates. The smallest functional unit of muscle force production. |
| Notch filter | A bandstop filter that attenuates a narrow frequency band (e.g., 60 Hz power line noise). |
| Packet | One chunk of data sent by the device over TCP. At 2000 Hz: 125 samples per channel, 16 packets per second. |
| pyqtgraph | Python library for fast scientific graphics, built on PyQt and numpy. |
| QThread | Qt's thread class. Allows background work while keeping the UI responsive. Communication back to the UI uses Qt signals/slots, which are thread-safe. |
| RMS | Root Mean Square: √(mean(x²)). A measure of signal power/amplitude that accounts for both positive and negative values. |
| Stage output | The Qt signal `stage_output(stage_name, array)` emitted by `DataReceiverThread` at each processing stage. |
| TKEO | Teager-Kaiser Energy Operator: Ψ(x[n]) = x[n]² − x[n−1]·x[n+1]. Amplifies sudden energy changes, useful for detecting muscle activation onset. |
| Zero-phase filter | A filter with zero phase distortion; achieved via `filtfilt`. All frequency components pass through with zero time shift. |

---

## 17. References

- Bonato, P., D'Alessio, T., & Knaflitz, M. (1998). A statistical method for the measurement of muscle activation intervals from surface myoelectric signal during gait. *IEEE Transactions on Biomedical Engineering*, 45(3), 287–299.
- De Luca, C.J. (1984). Myoelectrical manifestations of localized muscular fatigue in humans. *Critical Reviews in Biomedical Engineering*, 11(4), 251–279.
- De Luca, C.J. (1997). The use of surface electromyography in biomechanics. *Journal of Applied Biomechanics*, 13(2), 135–163.
- De Luca, C.J., Gilmore, L.D., Kuznetsov, M., & Roy, S.H. (2010). Filtering the surface EMG signal: Movement artifact and baseline noise contamination. *Journal of Biomechanics*, 43(8), 1573–1579.
- Hermens, H.J., Freriks, B., Disselhorst-Klug, C., & Rau, G. (2000). Development of recommendations for SENIAM surface electromyography sensors and sensor placement procedures. *Journal of Electromyography and Kinesiology*, 10(5), 361–374.
- Kaiser, J.F. (1990). On a simple algorithm to calculate the 'energy' of a signal. *Proceedings of ICASSP*, 381–384.
- Lindstrom, L., Kadefors, R., & Petersen, I. (1977). An electromyographic index for localized muscle fatigue. *Journal of Applied Physiology*, 43(4), 750–754.
- Merletti, R., & Roy, S.H. (1996). Myoelectric and mechanical manifestations of muscle fatigue in voluntary contractions. *Journal of Orthopaedic and Sports Physical Therapy*, 24(6), 342–353.
- Robinson, R.O., Herzog, W., & Nigg, B.M. (1987). Use of force platform variables to quantify the effects of chiropractic manipulation on gait symmetry. *Journal of Manipulative and Physiological Therapeutics*, 10(4), 172–176.
- Solnik, S., Rider, P., Steinweg, K., DeVita, P., & Hortobágyi, T. (2010). Teager-Kaiser energy operator signal conditioning improves EMG onset detection. *European Journal of Applied Physiology*, 110(3), 489–498.
