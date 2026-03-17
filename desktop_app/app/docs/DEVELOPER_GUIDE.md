# OTB-EMG App — Developer Guide

This document covers the architecture, communication protocol, signal processing pipeline, UI patterns, and development conventions for the `desktop_app/` codebase. Assumes familiarity with Python, PyQt5, and basic DSP concepts.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Entry Point and Wiring](#2-entry-point-and-wiring)
3. [Configuration System](#3-configuration-system)
4. [Device Communication Protocol](#4-device-communication-protocol)
5. [Live Data Pipeline](#5-live-data-pipeline)
6. [Signal Processing](#6-signal-processing)
7. [Calibration Flow](#7-calibration-flow)
8. [Recording and Session Persistence](#8-recording-and-session-persistence)
9. [UI Architecture](#9-ui-architecture)
   - [Window Hierarchy](#91-window-hierarchy)
   - [BaseTab Pattern](#92-basetab-pattern)
   - [Adding a New Tab](#93-adding-a-new-tab)
   - [Panel Pattern (Data Analysis)](#94-panel-pattern-data-analysis)
10. [Data Analysis Mode](#10-data-analysis-mode)
11. [Feature Extraction](#11-feature-extraction)
12. [Build System](#12-build-system)
13. [Dependency Rationale](#13-dependency-rationale)
14. [Glossary](#14-glossary)

---

## 1. Project Structure

```
desktop_app/
├── main.py                          Entry point, window wiring, device init, battery polling
├── build.py                         Runs PyInstaller with OTB-EMG.spec
├── OTB-EMG.spec                     PyInstaller build configuration
├── config.json                      All tunable parameters (loaded at runtime)
└── app/
    ├── core/
    │   ├── config.py                Config class — loads config.json, exposes as class attributes
    │   ├── device.py                SessantaquattroPlus — TCP protocol and command encoding
    │   ├── track.py                 Track — live plot with circular buffer
    │   ├── analysis_track.py        AnalysisTrack — static post-hoc plot
    │   └── paths.py                 Path resolution for frozen (PyInstaller) and source builds
    ├── data/
    │   ├── data_receiver.py         DataReceiverThread — background QThread, TCP reader
    │   └── csv_loader.py            CSVDataLoader — reads recorded CSV files
    ├── managers/
    │   ├── track_manager.py         Creates and manages live plot tracks
    │   ├── analysis_track_manager.py Manages analysis-mode plot tracks
    │   ├── recording_manager.py     Accumulates and writes CSV during recording
    │   ├── streaming_controller.py  Toggles receiver_thread.running, manages QTimer
    │   └── time_navigation_controller.py Slider + step controls for analysis mode
    ├── processing/
    │   ├── filters.py               Bandpass, notch, rectification, envelope filters
    │   ├── features.py              Post-hoc EMG feature extraction functions
    │   ├── pipeline.py              ProcessingPipeline registry (named pipelines)
    │   ├── realtime_detector.py     ContractionDetector — hysteresis-based live detection
    │   └── transforms.py            FFT transform
    └── ui/
        ├── windows/
        │   ├── main_window.py       SoundtrackWindow — live data window
        │   └── data_analysis_window.py DataAnalysisWindow
        ├── dialogs/
        │   └── dialogs.py           CalibrationDialog, ChannelSelectorDialog, TrackVisibilityDialog
        ├── tabs/
        │   ├── base_tab.py          Abstract BaseTab — enforces two-panel layout
        │   └── tab_implementations.py AllTracksTab, AccessoryTab, HDsEMGTab, HeatmapTab, IndividualChannelsTab, FeaturesTab
        └── panels/
            ├── data_viewing_panel.py Signal processing controls (analysis mode)
            └── features_panel.py    Feature extraction buttons (analysis mode)
```

---

## 2. Entry Point and Wiring

`main.py` is the sole entry point and the wiring layer. It follows a **lazy initialization** pattern for the device connection.

### Startup sequence

```
main()
├── SessantaquattroPlus(emulator_mode=...)   # device object, no socket yet
├── SelectionWindow()
├── DataAnalysisWindow()
├── SoundtrackWindow(device)
│
├── Wire SelectionWindow buttons → show/hide windows
├── Wire back buttons → return to selection
│
├── Wire live window buttons:
│   ├── connect_button    → handle_connect()
│   ├── stream_button     → handle_stream_toggle()
│   ├── record_button     → handle_record_toggle()
│   └── calibrate_button  → handle_calibration()
│
├── BatteryPoller (QTimer, 30 s interval) → HTTP GET to device gateway
└── app.exec_()
```

### Why buttons are wired in main.py, not SoundtrackWindow

`SoundtrackWindow` manages visualization. Opening a TCP socket, calling `sys.exit()` on connection failure, and coordinating device state are concerns of the application layer (`main.py`), not the window. Keeping them separate prevents the window from needing to know about connectivity.

### handle_connect() logic

1. Checks if the receiver thread is already running — skips reconnect if so.
2. Calls `device.create_command(FSAMP=2, NCH=3, ...)` — encodes the 16-bit configuration word.
3. Calls `device.start_server()` — binds port 45454, waits for device TCP connection (10 s timeout).
4. Calls `device.send_command(command)` — sends the 2-byte command to start streaming.
5. Calls `live_data_window.initialize_receiver()` or `reinitialize_receiver()`.

### Emulator mode

Set the environment variable `SESSANTAQUATTRO_EMULATOR=1` before launching to skip the WiFi network check. Useful for UI development without hardware.

```bash
set SESSANTAQUATTRO_EMULATOR=1
python main.py
```

### Battery polling

`BatteryPoller` uses a `QTimer` to spawn a daemon `threading.Thread` every 30 seconds that performs an HTTP GET to `http://192.168.1.1/` and parses the battery percentage from the HTML response. This is independent of the TCP data socket and does not interfere with EMG streaming.

---

## 3. Configuration System

All tunable parameters are stored in `desktop_app/config.json`. At startup, `app/core/config.py` loads this file and exposes every value as a class attribute on `Config`.

```python
from app.core.config import Config
Config.BANDPASS_LOW     # 20 Hz
Config.TKEO_K_THRESHOLD # 8.0
Config.UPDATE_RATE      # 16 ms
```

To change a parameter, edit `config.json` — do not hardcode values in source files. `Config` attributes are read once at module import time; changes to `config.json` require a restart.

### Path resolution

`app/core/paths.py` handles the difference between running from source and from a PyInstaller frozen build:

```python
get_base_dir()      # adjacent to exe (frozen) or desktop_app/ (source)
get_data_dir()      # base_dir/data/
get_recordings_dir()# base_dir/recordings/
get_config_path()   # base_dir/config.json
get_bundled_resource(rel) # sys._MEIPASS/rel (frozen) or base_dir/rel (source)
```

`config.json` is expected **next to the exe** (not inside `_MEIPASS`), making it user-editable after distribution. If `config.json` is absent, `Config` silently falls back to defaults coded into `config.py`.

---

## 4. Device Communication Protocol

### Network topology

The device creates a WiFi hotspot. The laptop connects to it and acts as the **TCP server**. The device connects as the **TCP client**. This is the reverse of the common client-server model.

```
Sessantaquattro+ (TCP client)
    connects to →
Laptop (TCP server, port 45454, 0.0.0.0)
```

### Connection sequence

1. `SessantaquattroPlus.start_server()` binds `0.0.0.0:45454` and calls `accept()` (10 s timeout).
2. Device connects; `accept()` returns the client socket.
3. `send_command(command)` transmits the 2-byte configuration word (big-endian, signed).
4. Device immediately begins streaming EMG data.

### Command encoding

The 16-bit command word is constructed by bitwise OR of field values:

```
Bit  0     : GO    — 1 = start streaming (must be 1)
Bit  1     : REC   — SD card recording (unused)
Bits 2–3   : TRIG  — trigger mode (0 = GO/STOP bit)
Bits 4–5   : EXTEN — extension (unused)
Bit  6     : HPF   — hardware high-pass filter (1 = 10.5 Hz)
Bit  7     : HRES  — resolution (0 = 16-bit, 1 = 24-bit)
Bits 8–10  : MODE  — working mode (0 = monopolar)
Bits 11–12 : NCH   — channel count selector
Bits 13–14 : FSAMP — sampling frequency selector
```

FSAMP and NCH mappings (monopolar mode):

| FSAMP | Frequency |   | NCH | Channels |
|---|---|---|---|---|
| 0 | 500 Hz | | 0 | 16 |
| 1 | 1000 Hz | | 1 | 24 |
| 2 | 2000 Hz | | 2 | 40 |
| 3 | 4000 Hz | | 3 | 72 (64 EMG + 8 AUX) |

Default: `FSAMP=2` (2000 Hz), `NCH=3` (72 channels), `MODE=0` (monopolar), `HPF=1`, `GO=1`.

### Packet format

At 2000 Hz, 72 channels:

```
Packet size = nchannels × 2 bytes × (frequency / 16 samples)
           = 72 × 2 × 125 = 18000 bytes per packet
Packet rate = 16 packets/second
```

Data layout: big-endian 16-bit signed integers, **interleaved by sample**:

```
[ch0_s0, ch1_s0, ..., ch71_s0,   ← sample 0, all channels
 ch0_s1, ch1_s1, ..., ch71_s1,   ← sample 1
 ...]
```

After `struct.unpack` and reshape: `(n_samples, nchannels)` → transpose → `(nchannels, n_samples)`. This column layout (channels as rows, time as columns) is used uniformly throughout the pipeline.

### Battery query

`SessantaquattroPlus.get_battery_level()` performs an HTTP GET to `http://192.168.1.1/` and parses:

```html
<td>Battery Level:</td><td>NN%</td>
```

Returns an integer 0–100, or `None` on failure. Does not require the TCP data socket.

---

## 5. Live Data Pipeline

```
Device (WiFi/TCP)
    │ 18000 bytes/packet, 16 packets/s
    ▼
DataReceiverThread  (background QThread, alive for entire session)
    │
    │  socket.recv() → accumulate in buffer
    │  when buffer >= expected_bytes:
    │    struct.unpack → reshape → (nchannels, n_samples)
    │
    ├── emit stage_output('raw', data)
    │
    ├── filtered = Pipeline('filtered').run(data)
    ├── emit stage_output('filtered', filtered)
    │
    ├── rectified = Pipeline('rectified').run(filtered)
    ├── emit stage_output('rectified', rectified)
    │
    ├── processed = Pipeline('final').run(data)   ← runs on raw data
    ├── emit stage_output('final', processed)
    │
    └── if self.running:
          track.feed(processed) for each Track

stage_output consumers:
    RecordingManager.on_data_for_recording   ← 'raw' stage only; writes when is_recording
    CalibrationDialog.on_stage_output        ← 'filtered' stage only; during calibration only

StreamingController:
    start_streaming() → receiver_thread.running = True, QTimer.start(16 ms)
    stop_streaming()  → receiver_thread.running = False, QTimer.stop()

QTimer (16 ms):
    SoundtrackWindow.update_plot()
        TrackManager.draw_all_tracks()
        update_heatmap()
```

### Why the thread is never restarted

`DataReceiverThread` blocks in `socket.recv()` for the entire session. `StreamingController` only toggles `running` to pause/resume data feeding. This avoids re-establishing the TCP connection on each pause/resume, which the device firmware may not handle reliably.

When `running=False`, the thread still reads from the socket (discards packets) to prevent the device's TCP send buffer from filling up and stalling the connection.

### Pipeline registry

`app/processing/pipeline.py` maintains a module-level dictionary of named `ProcessingPipeline` objects. Each pipeline is a list of callables applied in sequence to a `(nchannels, n_samples)` array.

| Pipeline | Stages |
|---|---|
| `filtered` | butter_bandpass(20–450 Hz) → notch(60 Hz) |
| `rectified` | abs() |
| `final` | passthrough (runs on raw data; reserved for future use) |
| `fft` | FFT transform |

The `final` pipeline runs on raw (`data`), not `filtered`, so that "All Tracks" shows the unprocessed waveform. The filtered stage is available separately.

---

## 6. Signal Processing

All filter functions are in `app/processing/filters.py`. Coefficient design uses `scipy.signal.butter` and filtering uses `scipy.signal.filtfilt` (zero-phase, non-causal) for post-hoc use. For real-time use in the live pipeline, the same filters are applied per-packet with the live `sosfilt` path.

### Bandpass: 20–450 Hz, 4th-order Butterworth

Removes motion artifact and baseline drift below 20 Hz, and high-frequency noise above 450 Hz. Applied to the `filtered` pipeline stage.

### Notch: 60 Hz, Q=30

Removes North American power line interference. Q=30 yields a 2 Hz passband, leaving adjacent frequency content intact.

### Rectification

`abs(data)` converts the bipolar signal to a positive-only signal. Full-wave rectification is the prerequisite for RMS envelope extraction.

### Envelope

Two envelope options are available in analysis mode:
- **RMS** (sliding window, default 50 samples = 25 ms at 2000 Hz): local signal power
- **Lowpass** (4th-order Butterworth, default 10 Hz, zero-phase): smoothed amplitude

### Heatmap RMS

`update_heatmap()` in `SoundtrackWindow` reads the last 100 samples from the HD-sEMG track buffer, excludes saturated samples (`|x| > 32760`), computes per-channel RMS, then normalizes:

```python
normalized_rms = current_rms[:64] / (mvc_rms[:64] + 1e-10)
normalized_rms = np.clip(normalized_rms, 0, 1)
```

The `1e-10` prevents division by zero. Values above 1.0 are clipped to 1.0.

### Channel-to-grid mapping

```
channel_idx = col * 8 + (7 - row)
```

Channel 0 is at bottom-left. Channels increase upward within each column, then left-to-right across columns (column-major, bottom-left origin).

---

## 7. Calibration Flow

`CalibrationDialog` is a modal dialog that subscribes to `stage_output('filtered', ...)` during the collection phases.

### Procedure

1. **Rest phase** (5 s, `Config.REST_DURATION`): collects per-packet filtered RMS per channel.
2. **Contraction phase** (5 s, `Config.CONTRACTION_DURATION`): same collection under MVC effort.

### Threshold computation

```python
baseline_rms  = mean(rest_rms_samples, axis=time)          # shape (nchannels,)
baseline_std  = std(rest_rms_samples, axis=time)
threshold     = baseline_rms + Config.BASELINE_THRESHOLD_MULT * baseline_std  # 3.0σ
mvc_rms       = percentile(contraction_rms_samples, Config.MVC_PERCENTILE, axis=time)  # 99th
```

### Saturation handling

Samples where `|x| > Config.SATURATION_HIGH` (32760) indicate a railing electrode — physically disconnected or poorly contacted. These are excluded from all RMS calculations.

Channels where all contraction samples are saturated receive `mvc_rms = 0`. These are spatially interpolated: the channel value is replaced with the mean of its non-saturated 8×8 grid neighbors.

Channels where `mvc_rms < 0.10 × median(mvc_rms)` are also treated as bad and interpolated.

### Signal emission

`CalibrationDialog` emits `calibration_complete(baseline_rms, threshold, mvc_rms)` as a Qt signal on success. `SoundtrackWindow.on_calibration_complete()` stores these arrays and calls `save_session_data()`.

---

## 8. Recording and Session Persistence

### Recording

`RecordingManager` connects to `stage_output('raw', ...)` and accumulates data in a pre-allocated numpy array. Recording begins and ends via `start_recording()` / `stop_recording()`. On stop, the array is written to a timestamped CSV file at `get_recordings_dir()`.

- **Max samples**: `Config.MAX_RECORDING_SAMPLES` = 1,000,000. Overflow triggers a warning dialog and stops recording automatically.
- **Channels saved**: first 64 channels only (`data[:Config.EMG_CHANNELS, :]`), discarding the 8 auxiliary channels.

### Session persistence

`SoundtrackWindow.save_session_data()` writes the three calibration arrays to `data/previous_session.csv` at `get_data_dir()`. Values are serialized as comma-separated floats within a CSV cell.

`load_session_data()` is called inside `SoundtrackWindow.__init__()` **before any widgets are created**. This sets `self.is_calibrated = True` before the UI exists. UI elements that depend on calibration state must check `self.is_calibrated` at creation time, not in `load_session_data()`.

---

## 9. UI Architecture

### 9.1 Window Hierarchy

```
SelectionWindow          (400×300, startup mode selector)
    │
    ├── SoundtrackWindow (1200×800, live data mode)
    │       ├── Back button row
    │       ├── Top control bar: Connect, Calibrate, Stream, Record, Battery, Contraction
    │       └── QTabWidget
    │             ├── AllTracksTab           scrollable list of all EMG track plots
    │             ├── AccessoryTab           auxiliary channels (AUX 1–8)
    │             ├── HDsEMGTab              HD-sEMG averaged channel view
    │             ├── HeatmapTab             8×8 normalized activation heatmap
    │             ├── IndividualChannelsTab  single-channel detail view
    │             └── FeaturesTab            live rolling feature plots
    │
    └── DataAnalysisWindow (1200×800, post-hoc analysis mode)
            ├── Back button row
            ├── File controls row (Load File 1, Load File 2)
            ├── Time navigation row (slider, step buttons, window size input)
            └── QSplitter (vertical)
                  ├── Top: plot area (left) + QTabWidget control panel (right, 250px)
                  │         ├── DataViewingPanel   (channel select, processing controls)
                  │         └── FeaturesPanel      (feature analysis buttons)
                  └── Bottom: results text panel (monospace, read-only)
```

### 9.2 BaseTab Pattern

All live-mode tabs subclass `BaseTab` (`app/ui/tabs/base_tab.py`), which enforces a horizontal two-panel layout:

```
┌──────────────────────────────────┬───────────────────┐
│                                  │                   │
│  Content Area (stretch=3)        │  Control Panel    │
│  - main visualization            │  (max 200px wide) │
│  - usually scrollable            │  - buttons        │
│                                  │                   │
└──────────────────────────────────┴───────────────────┘
```

Subclasses must implement three methods:

```python
def create_content_area(self) -> QtWidgets.QWidget: ...
def create_control_panel(self) -> QtWidgets.QWidget: ...
def get_tab_name(self) -> str: ...
```

Optionally override:

```python
def connect_signals(self, window): ...  # called by SoundtrackWindow._connect_signals()
```

**Critical**: initialize instance variables before calling `super().__init__(parent)`, because `__init__` calls both `create_content_area()` and `create_control_panel()` immediately.

Utility methods provided by `BaseTab`:
- `self.create_scroll_area()` → `(QScrollArea, QWidget, QVBoxLayout)` — standard scrollable content area
- `self.create_control_panel_base(buttons=[...])` → `QWidget` — standard right-panel with stretch at bottom

### 9.3 Adding a New Tab

**Step 1**: Create the tab class in `app/ui/tabs/tab_implementations.py`:

```python
from app.ui.tabs.base_tab import BaseTab
from PyQt5 import QtWidgets

class MyNewTab(BaseTab):
    def __init__(self, parent=None):
        self.my_button = None         # init attrs BEFORE super().__init__
        super().__init__(parent)

    def create_content_area(self) -> QtWidgets.QWidget:
        scroll_area, scroll_widget, self.scroll_layout = self.create_scroll_area()
        # add widgets to self.scroll_layout
        return scroll_area

    def create_control_panel(self) -> QtWidgets.QWidget:
        self.my_button = QtWidgets.QPushButton("Do Something")
        return self.create_control_panel_base([self.my_button])

    def get_tab_name(self) -> str:
        return "My Tab"

    def connect_signals(self, window):
        self.my_button.clicked.connect(window.on_my_button_clicked)
```

**Step 2**: Add to `SoundtrackWindow._create_tabs()` in `main_window.py`:

```python
from app.ui.tabs.tab_implementations import MyNewTab

self.my_tab = MyNewTab()
self.tabs.addTab(self.my_tab, self.my_tab.get_tab_name())
```

**Step 3**: Add the handler method to `SoundtrackWindow`:

```python
def on_my_button_clicked(self):
    ...
```

Buttons must be stored as `self.` attributes on the tab so the parent window can wire signals to them after construction. Signals are wired in `connect_signals(window)`, not in the tab's `__init__`.

**Accessing tab internals** (e.g., for TrackManager):

```python
self.all_tracks_tab.scroll_layout       # QVBoxLayout inside the scroll area
self.my_tab.my_button                   # access any stored widget attribute
```

### 9.4 Panel Pattern (Data Analysis)

`DataAnalysisWindow` uses standalone panel classes because the plot area is shared across tabs — only the control panel switches. Panels are plain `QWidget` subclasses, not `BaseTab`:

```python
class MyPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.my_button = QtWidgets.QPushButton("Compute")
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.my_button)
        layout.addStretch()
```

Add to `DataAnalysisWindow`:

```python
self.my_panel = MyPanel()
self.content_tabs.addTab(self.my_panel, "My Analysis")
self.my_panel.my_button.clicked.connect(self._on_my_analysis)
```

---

## 10. Data Analysis Mode

`DataAnalysisWindow` is fully independent of the live mode. No device connection is needed.

### Data loading

`CSVDataLoader.load_file()` reads a recorded CSV and returns:
- `data`: numpy array `(nchannels, n_samples)`
- `timestamps`: 1D array of timestamps
- `sample_rate`: estimated from median inter-sample interval

Timestamp handling:
1. **Duplicated timestamps**: if the CSV recorded one timestamp per packet (not per sample), timestamps are linearly interpolated.
2. **Non-monotonic timestamps**: non-increasing entries are discarded before sample rate estimation.

### Time navigation

`TimeNavigationController` manages the current view window (start time + duration):
- Slider: 1000 steps across the full recording duration
- `<` / `>` buttons: step by 10% of current window duration
- Window size input: free text, validated to [0.1, 1000] seconds

### Signal processing controls

`DataViewingPanel` exposes channel selection, rectification, and envelope computation. Processing is applied on-demand when controls change — the underlying loaded data is not modified.

---

## 11. Feature Extraction

All feature functions are in `app/processing/features.py`. They are **post-hoc only** (use `filtfilt`, non-causal) and must not be used for real-time processing.

### Shared timestamp preprocessing

Every `compute_*` function runs the same preprocessing on the input timestamp array before any signal processing:

1. Remove NaN entries from both `signal` and `timestamps`.
2. Detect and interpolate duplicated timestamps (packet-level timestamps → sample-level).
3. Enforce strictly increasing timestamps (discard non-increasing entries).
4. Re-estimate sample rate from median inter-sample interval of the cleaned timestamps.

The re-estimated sample rate is what all subsequent filter design uses — not the nominal sample rate argument. This makes the functions robust to CSV files with imperfect timestamps.

### TKEO activation timing

`compute_tkeo_activation_timing()` → `TKEOResult`

Pipeline:
1. Bandpass filter (20–450 Hz, 4th-order Butterworth, zero-phase)
2. TKEO: `Ψ(x[n]) = x[n]² − x[n−1]·x[n+1]`
3. Rectify: `|TKEO|`
4. Smooth: lowpass at 10 Hz (zero-phase)
5. Baseline: mean and std of first 0.5 s
6. Detection threshold: `max(baseline_mean + 8·σ, max_envelope / 4)`
7. Find peaks above threshold with minimum 0.5 s separation (`scipy.signal.find_peaks`)
8. Backtrack each peak to true onset: walk backward until envelope < `baseline_mean + 3·σ`
9. Deduplicate onsets (multiple peaks can map to the same onset)

Returns: timestamps of onset events, TKEO envelope, thresholds.

### Burst duration

`compute_burst_duration()` → `BurstDurationResult`

Same TKEO pipeline. Instead of peak detection, detects threshold crossings of the low backtrack threshold:
- **Onset**: rising edge above `baseline_mean + 3·σ`
- **Offset**: falling edge below `baseline_mean + 3·σ`

Only bursts whose peak TKEO exceeds the higher detection threshold and whose duration exceeds 50 ms are counted.

Returns: burst count, mean duration ± std, individual burst durations.

### Bilateral symmetry

`compute_bilateral_symmetry()` → `BilateralSymmetryResult`

1. Align both signals to relative time (t=0).
2. Trim to overlapping duration.
3. Resample both to the lower of the two sample rates via `scipy.signal.resample`.
4. Sliding-window SI: `(RMS₁ − RMS₂) / (RMS₁ + RMS₂)`, 250 ms window, 50 ms step.

Returns: SI time series, mean SI, std SI, max asymmetry, overall RMS of each file.

### Fatigue

`compute_fatigue()` → `FatigueResult`

Two parallel sliding-window analyses (500 ms window, 100 ms step):

**RMS track**: rectified signal RMS per window. Fatigue flagged when `(RMS - baseline_RMS) / baseline_RMS ≥ 0.317` (31.7% increase from baseline).

**Median frequency track**: `compute_mf_rate()` per window using Hamming-windowed FFT. MF rate (Hz/s) computed as point-to-point derivative. Fatigue flagged when `rate ≤ −0.89 Hz/s`.

Returns: RMS time series, MF time series, timestamps where each fatigue criterion is met.

### Centroid shift (HD-EMG)

`compute_centroid_shift()` → `CentroidShiftResult`

Requires 64-channel input. Per sliding window (500 ms, 100 ms step):
1. Compute per-channel RMS → use as spatial weights on the 8×8 grid.
2. Centroid: `cx = Σ(col · w) / Σw`, `cy = Σ(row · w) / Σw`.
3. Displacement: Euclidean distance from initial centroid.

Returns: centroid trajectory, displacement time series, total shift, mean drift rate (electrode-units/s).

### Spatial non-uniformity (HD-EMG)

`compute_spatial_nonuniformity()` → `SpatialNonUniformityResult`

Requires 64-channel input. Per sliding window (500 ms, 100 ms step), three metrics from the per-channel RMS distribution:

- **CV**: `std(w) / mean(w)` — coefficient of variation. Higher = more uneven activation.
- **Shannon entropy**: `−Σ p·log₂(p + ε)`, where `p = w / Σw`. Higher = more uniform distribution (max 6 bits for 64 channels).
- **Activation fraction**: fraction of channels with RMS > threshold. If calibration thresholds are provided, uses them per-channel; otherwise uses the per-window mean.

---

## 12. Build System

The app is built into a distributable Windows folder using PyInstaller.

### Running a build

From `desktop_app/`:

```bash
python build.py
# or directly:
python -m PyInstaller --clean --noconfirm OTB-EMG.spec
```

Output: `desktop_app/dist/OTB-EMG/` — distribute the entire folder.

### OTB-EMG.spec

Key spec decisions:
- `SPECPATH` is used instead of `os.getcwd()` to reliably resolve paths relative to the spec file itself, regardless of the working directory at build time.
- `hiddenimports` lists scipy submodules that PyInstaller's static analysis fails to detect.
- `upx=False` — executable compression is disabled to prevent antivirus false positives.
- `console=False` — no terminal window on launch.
- One-folder mode (`exclude_binaries=True` + `COLLECT`) rather than single-file, for faster startup and easier patching.

### What to distribute alongside the exe

After building, `dist/OTB-EMG/` contains the executable and all bundled libraries. Additionally copy:
- `config.json` — must be placed **next to** `OTB-EMG.exe` (not inside `_internal/`). It is loaded via `get_config_path()` → `os.path.dirname(sys.executable)`.
- `recordings/` directory (optional, created automatically on first recording if absent).

---

## 13. Dependency Rationale

| Library | Used for | Why |
|---|---|---|
| PyQt5 | UI framework, threading | Mature, cross-platform; `QThread` + `pyqtSignal` provide thread-safe main-thread communication from background workers |
| pyqtgraph | Real-time plot rendering | Orders of magnitude faster than matplotlib for continuously updated plots; uses OpenGL where available |
| numpy | All array operations | Vectorized; `np.ndarray` is the universal data type throughout the pipeline |
| scipy | Filter design, FFT, resampling, peak finding | Trusted, well-validated DSP implementations; used post-hoc only (not required for Android port) |

---

## 14. Glossary

| Term | Definition |
|---|---|
| ADC | Analog-to-Digital Converter. 16-bit: range −32768 to +32767. |
| Butterworth filter | Filter with maximally flat (ripple-free) passband. |
| Circular buffer | Fixed-size array used as a ring — new data overwrites the oldest when full. |
| filtfilt | Zero-phase filtering: forward then backward pass cancels phase distortion. Non-causal; requires the full signal. |
| HD-sEMG | High-density surface EMG — array of many closely spaced electrodes capturing spatial muscle activity distribution. |
| MVC | Maximum Voluntary Contraction. Used as a normalization reference for heatmap display. |
| Motor unit | One motor neuron and all the muscle fibers it innervates. The smallest unit of force production. |
| Packet | One TCP chunk from the device. At 2000 Hz, 72 channels: 18000 bytes, 125 samples/channel, 16 packets/s. |
| Pipeline | Named sequence of processing stages applied to each incoming data packet. |
| QThread | Qt thread class. Emits signals to communicate results back to the UI thread safely. |
| RMS | Root Mean Square: √(mean(x²)). Measures signal power/amplitude. |
| Stage output | `stage_output(stage_name, array)` signal emitted by `DataReceiverThread` at each processing stage. |
| TKEO | Teager-Kaiser Energy Operator: Ψ(x[n]) = x[n]² − x[n−1]·x[n+1]. Amplifies sudden energy changes. |
| Zero-phase filter | Applied via `filtfilt`; all frequencies pass with zero time shift. |
