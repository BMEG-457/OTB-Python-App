# Android Port Plan — OTB EMG App

## Table of Contents
1. [What This Plan Is](#what-this-plan-is)
2. [Key Concepts for Beginners](#key-concepts-for-beginners)
3. [What Gets Reused vs. Rewritten](#what-gets-reused-vs-rewritten)
4. [Architecture of the Android App](#architecture-of-the-android-app)
5. [Phase 1 — Development Environment Setup](#phase-1--development-environment-setup)
6. [Phase 2 — Project Structure](#phase-2--project-structure)
7. [Phase 3 — Port the Core Layer](#phase-3--port-the-core-layer)
8. [Phase 4 — Port the Processing Layer](#phase-4--port-the-processing-layer)
9. [Phase 5 — Port the Manager Layer](#phase-5--port-the-manager-layer)
10. [Phase 6 — Build the UI with Kivy](#phase-6--build-the-ui-with-kivy)
11. [Phase 7 — Package for Android with Buildozer](#phase-7--package-for-android-with-buildozer)
12. [Phase 8 — Testing](#phase-8--testing)
13. [Known Risks & Resolutions](#known-risks--resolutions)

---

## What This Plan Is

The desktop app (`BMEG 457 scripts/`) is a Python application built with PyQt5 (a desktop GUI
library) that connects to a Sessantaquattro+ EMG device over WiFi, receives raw muscle signal
data in real time, processes it, and displays it with charts.

This plan describes how to port that app to an Android phone. The goal is a Kivy-based Android
app that can:
- Connect to the Sessantaquattro+ over WiFi, the same way the desktop app does
- Stream, record, and visualize live EMG data
- Run the same signal-processing algorithms (filtering, feature extraction)
- Export recordings to CSV on the phone

---

## Key Concepts for Beginners

### PyQt5 (the existing desktop framework)
PyQt5 is a Python library for building desktop windows. It provides buttons, labels, text
boxes, and a system for widgets to talk to each other ("signals and slots"). It is
**desktop-only** — it cannot run on Android. This is the main reason a rewrite is needed.

### Kivy (the Android framework we will use)
Kivy is a Python library for building apps that work on both desktop and Android. Instead of
PyQt5 widgets, it has its own set of UI building blocks (called "widgets" as well, but
different ones). The core idea is the same: lay out buttons, labels, and plots on screen and
respond to user taps.

### python-for-android (p4a)
This is the tool that takes Python code and all its dependencies and compiles them into a
format that Android understands. It is a lower-level tool; most developers don't use it
directly — they use Buildozer, which calls p4a automatically.

### Buildozer
Buildozer is a command-line tool that packages a Kivy app into an `.apk` file (the Android
installer). You point it at your project, list your dependencies in a `buildozer.spec` file,
and it compiles everything. It **only runs on Linux**. Windows users must use WSL.

### WSL (Windows Subsystem for Linux)
WSL lets you run a Linux terminal inside Windows. Buildozer needs Linux, so you will install
WSL, then run Buildozer inside WSL while your code stays on your Windows filesystem.

### QThread vs. threading.Thread
PyQt5 uses "QThread" to run things in the background (so the UI doesn't freeze while waiting
for data). Standard Python also has background threads via the `threading` module. In the
Android app, QThread is replaced with `threading.Thread`.

### TCP Server / Client model
The Sessantaquattro+ device connects *to* the app (it is the client). The app runs a TCP
*server* that waits for the device to connect. This is already how the desktop app works.
On Android the phone acts as the server — nothing about this logic changes, only the platform
running it.

---

## What Gets Reused vs. Rewritten

### Keep (platform-agnostic Python, no changes needed)

| File | Why it can stay |
|------|----------------|
| `app/processing/pipeline.py` | Pure Python, no UI, no scipy |
| `app/processing/transforms.py` | Pure numpy, no UI |
| `app/core/device.py` | Standard Python sockets (minor changes — see Phase 3) |

### Modified (needed changes to remove scipy or PyQt5)

| File | What changed |
|------|-------------|
| `app/processing/filters.py` | Removed scipy; uses pre-computed coefficients from `config.py` + `iir_filter.filtfilt` |
| `app/processing/features.py` | Removed `scipy.signal` and `scipy.fft`; uses `iir_filter` + `np.fft` |
| `app/core/config.py` | Expanded: all tunable params + pre-computed Butterworth b/a arrays |

### New files created (did not exist in desktop app)

| File | Purpose |
|------|---------|
| `app/processing/iir_filter.py` | Pure-numpy `lfilter`, `filtfilt`, `find_peaks`, `resample_signal` — replaces scipy |
| `scripts/compute_filter_coeffs.py` | Offline script (run on desktop with scipy) to regenerate filter coefficients |

### Must be rewritten (desktop-only code)

| File | Reason it must change | Android replacement |
|------|----------------------|---------------------|
| `main.py` | PyQt5 `QApplication` entry point | Kivy `App` entry point |
| `app/ui/windows/main_window.py` | PyQt5 widgets and pyqtgraph plots | Kivy screens + pure Kivy canvas |
| `app/ui/windows/data_analysis_window.py` | PyQt5 widgets | Kivy screen |
| `app/ui/tabs/tab_implementations.py` | PyQt5 + pyqtgraph tabs | Kivy tab panels |
| `app/ui/dialogs/dialogs.py` | PyQt5 dialogs | Kivy Popup widgets |
| `app/data/data_receiver.py` | Uses `QThread` and `pyqtSignal` | Uses `threading.Thread` + callbacks |
| `app/managers/recording_manager.py` | Uses `QObject`/`pyqtSignal` | Plain Python class with callbacks |
| `app/managers/streaming_controller.py` | Uses PyQt5 `QTimer` | Uses Kivy `Clock` |
| `app/managers/track_manager.py` | Uses PyQt5 | Not ported — tracks replaced by direct callbacks |
| `app/core/track.py` | Tied to pyqtgraph plot objects | Not ported — UI reads data directly |

---

## Architecture of the Android App

```
┌─────────────────────────────────────────────────────────────────┐
│                         Kivy UI Layer                           │
│  SelectionScreen | LiveDataScreen | DataAnalysisScreen          │
│  (Kivy widgets, pure Kivy canvas plot, Kivy Popups)             │
└────────────────────────────┬────────────────────────────────────┘
                             │ calls / callbacks
┌────────────────────────────▼────────────────────────────────────┐
│                        Manager Layer                            │
│  RecordingManager | StreamingController                         │
│  (plain Python — no Qt, no Kivy dependency)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │ calls
┌────────────────────────────▼────────────────────────────────────┐
│                    Data & Core Layer                            │
│  DataReceiverThread (threading.Thread) | device.py (sockets)   │
└────────────────────────────┬────────────────────────────────────┘
                             │ calls
┌────────────────────────────▼────────────────────────────────────┐
│                     Processing Layer                            │
│  filters.py | features.py | pipeline.py | transforms.py         │
│  iir_filter.py (pure numpy — no scipy)                          │
└─────────────────────────────────────────────────────────────────┘
```

Data flows upward: the device sends raw bytes → DataReceiverThread decodes and processes them
→ calls a callback → managers update state → Kivy UI re-draws the plot.

---

## Phase 1 — Development Environment Setup

**Goal:** Get a working Android build environment and a desktop test environment.

### Step 1.1 — Install WSL2
Open PowerShell as Administrator:
```powershell
wsl --install
```
Restart when prompted. On first WSL launch, create a Linux username and password.

### Step 1.2 — Install system dependencies in WSL

> **Note:** Do not use `pip3 install buildozer`. Ubuntu marks system Python as
> externally-managed in recent versions, causing a hard error. Use `pipx` instead.

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git \
    zip unzip openjdk-17-jdk autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake \
    libffi-dev libssl-dev pipx cython3
pipx ensurepath && source ~/.bashrc
```

### Step 1.3 — Install Buildozer via pipx

```bash
pipx install buildozer
pipx inject buildozer setuptools appdirs colorama jinja2 "sh>=1.10,<2.0" build toml packaging cython
```

The `inject` step is required because Python 3.12 removed the `distutils` module that older
buildozer versions depend on. `setuptools` provides the shim. The other packages are runtime
dependencies that buildozer expects to find in its own environment.

### Step 1.4 — Required environment variable

Every buildozer command must be prefixed with `VIRTUAL_ENV=1`:
```bash
VIRTUAL_ENV=1 buildozer android debug
```

Without this, buildozer passes `--user` to pip inside its pipx venv, which fails with
`Cannot perform --user install`. Setting `VIRTUAL_ENV=1` tells buildozer it is already
inside a virtual environment and suppresses the flag.

This is controlled by a check at line 720 of `android.py` in the buildozer pipx venv:
```python
options = ["--user"]
if "VIRTUAL_ENV" in os.environ or "CONDA_PREFIX" in os.environ:
    options = []
```

### Step 1.5 — Create a symlink to avoid spaces in the build path

p4a rejects project paths that contain spaces. The project directory name must have no spaces.
This project uses `mobile_app/` (underscore) which is fine. If the path to your project
through Windows contains spaces, create a symlink:
```bash
ln -s "/mnt/c/path/to/mobile_app" ~/otb-mobile
cd ~/otb-mobile
```
Always run buildozer from the symlink path, not the `/mnt/c/...` path directly.

### Step 1.6 — Install the Android SDK and NDK (automated)
Buildozer downloads the Android SDK and NDK automatically on first build. You do not need
to install them manually. The first build will download several gigabytes and takes
**30–60 minutes** total.

### Step 1.7 — Desktop Python environment (for smoke testing before Android)

> **Critical:** Kivy does not support Python 3.14 (as of early 2026). You must use
> Python 3.12 for the desktop development environment.

Install Python 3.12 alongside your existing Python (Windows):
```powershell
winget install Python.Python.3.12
```

Create a virtual environment in the `mobile_app/` directory:
```powershell
cd mobile_app
py -3.12 -m venv .venv
.venv\Scripts\activate
```

Install Kivy using the official pre-built wheel index (do **not** use plain `pip install kivy`
— it tries to build from source and fails on Windows):
```powershell
pip install "kivy[base]" --extra-index-url https://kivy.org/downloads/simple/
pip install kivy_matplotlib_widget matplotlib numpy scipy
```

### Step 1.8 — Enable USB debugging on your Android phone
1. Go to **Settings → About Phone** and tap **Build Number** seven times.
2. Go to **Settings → Developer Options** and turn on **USB Debugging**.
3. Connect your phone via USB and tap "Allow" when prompted.

### Step 1.9 — Install ADB in WSL
```bash
sudo apt install adb
adb devices   # should list your phone's serial number
```

---

## Phase 2 — Project Structure

**Goal:** Create a clean directory layout for the Android app.

> **Important:** The directory must be named `mobile_app/` (underscore, not space).
> p4a rejects any path component that contains a space.

```
mobile_app/
├── PLAN.md                        ← this file
├── BUILDOZER_CONTEXT.md           ← build environment reference
├── buildozer.spec                 ← Buildozer configuration
├── main.py                        ← Kivy app entry point
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              ← constants + pre-computed filter coefficients
│   │   ├── device.py              ← ported from desktop (Phase 3)
│   │   └── paths.py               ← Android-aware path resolution
│   ├── data/
│   │   ├── __init__.py
│   │   └── data_receiver.py       ← ported from desktop (Phase 3)
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── iir_filter.py          ← pure-numpy scipy replacement (NEW — Phase 4)
│   │   ├── filters.py             ← modified to use iir_filter (Phase 4)
│   │   ├── features.py            ← modified to use iir_filter + np.fft (Phase 4)
│   │   ├── pipeline.py            ← copied verbatim
│   │   └── transforms.py          ← copied verbatim
│   ├── managers/
│   │   ├── __init__.py
│   │   ├── recording_manager.py   ← ported (Phase 5)
│   │   └── streaming_controller.py← ported (Phase 5)
│   └── ui/
│       ├── __init__.py
│       ├── screens/
│       │   ├── __init__.py
│       │   ├── selection_screen.py
│       │   ├── live_data_screen.py
│       │   └── data_analysis_screen.py
│       └── widgets/
│           ├── __init__.py
│           ├── emg_plot_widget.py     ← pure Kivy canvas (no matplotlib)
│           └── calibration_popup.py   ← calibration dialog
├── scripts/
│   └── compute_filter_coeffs.py   ← run on desktop to regenerate filter coefficients
└── tests/
    ├── test_processing.py
    └── test_networking.py
```

---

## Phase 3 — Port the Core Layer

**Goal:** Make device communication and the data receiver work without PyQt5.

### 3.1 — Port `app/core/device.py`

Replace all `sys.exit(1)` calls with `raise ConnectionError("message")` so the UI can
catch and display errors instead of silently crashing the app.

```python
# Before (desktop):
sys.exit(1)

# After (Android):
raise ConnectionError("Not connected to the Sessantaquattro+ WiFi network.")
```

The rest of the socket logic is unchanged — Python's `socket` module works on Android.

### 3.2 — Port `app/data/data_receiver.py`

Replace `QThread` (PyQt5) with `threading.Thread` (standard library). Replace `pyqtSignal`
with plain Python callbacks passed as constructor arguments.

```python
# Before (desktop):
class DataReceiverThread(QThread):
    stage_output = pyqtSignal(str, np.ndarray)
    def run(self):
        self.stage_output.emit('raw', data)

# After (Android):
class DataReceiverThread(threading.Thread):
    def __init__(self, device, client_socket, on_stage=None, on_error=None, on_status=None):
        super().__init__(daemon=True)
        self.on_stage = on_stage
    def run(self):
        if self.on_stage:
            self.on_stage('raw', data)
```

To update the Kivy UI from the background thread, always wrap UI calls in
`Clock.schedule_once()`:
```python
from kivy.clock import Clock

def on_stage(stage, data):
    if stage == 'final':
        data_copy = data.copy()
        Clock.schedule_once(lambda dt: widget.update(data_copy), 0)
```

### 3.3 — Port `app/core/paths.py`

On Android, apps cannot write to arbitrary directories. Use the Kivy app's private storage:

```python
def get_data_dir():
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app is not None:
            return app.user_data_dir
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "OTB_EMG_Data")
```

---

## Phase 4 — Port the Processing Layer

**Goal:** Make all signal processing work on Android without scipy.

> **Why scipy cannot be used on Android:** scipy has Fortran extensions that require
> `gfortran` to compile for ARM. The NDK versions that include `gfortran` (r21e and older)
> are no longer maintained and produce broken builds on modern Ubuntu. Removing scipy
> is the only reliable solution.

### 4.1 — Create `app/processing/iir_filter.py`

This new file provides pure-numpy replacements for every scipy function used in the app:

| scipy function | iir_filter replacement |
|---|---|
| `scipy.signal.lfilter(b, a, x)` | `iir_filter.lfilter(b, a, x)` |
| `scipy.signal.filtfilt(b, a, x)` | `iir_filter.filtfilt(b, a, x)` |
| `scipy.signal.find_peaks(x, ...)` | `iir_filter.find_peaks(x, ...)` |
| `scipy.signal.resample(x, n)` | `iir_filter.resample_signal(x, n)` |

`iir_filter.filtfilt` uses reflect padding (length `3 * max(len(a), len(b))`), matching
scipy's default. `iir_filter.find_peaks` returns `(indices, {})` matching scipy's interface.
`iir_filter.resample_signal` uses linear interpolation (adequate for RMS-based bilateral
symmetry; not as accurate as scipy's FFT-based resample for audio).

### 4.2 — Pre-compute filter coefficients in `app/core/config.py`

`scipy.signal.butter` is used only at coefficient design time. Coefficients are computed
once on the desktop, stored as constants in `config.py`, and used at runtime on Android.

Pre-computed at **DEVICE_SAMPLE_RATE = 2000 Hz** (FSAMP=2, MODE=0):

| Config key | Filter | Use |
|---|---|---|
| `BANDPASS_4_B/A` | butter(4, [20, 450] Hz, band) | Live pipeline + post-session analysis |
| `BANDPASS_1_B/A` | butter(1, [20, 450] Hz, band) | Short-data fallback in `butter_bandpass` |
| `LOWPASS_10_4_B/A` | butter(4, 10 Hz, low) | TKEO envelope smoothing |
| `NOTCH_60_B/A` | butter(2, 60 Hz notch, Q=30) | Power-line notch in live pipeline |

To regenerate coefficients for a different sample rate, run on a desktop with scipy:
```bash
python scripts/compute_filter_coeffs.py --fs 4000
# paste output into the FILTER COEFFICIENTS section of config.py
```

### 4.3 — Update `app/processing/filters.py`

Replace scipy imports with `iir_filter`. The function signatures (`butter_bandpass`,
`notch`, `rectify`) are unchanged — callers do not need updating.

### 4.4 — Update `app/processing/features.py`

Replace:
- `from scipy.signal import butter, filtfilt, find_peaks, resample` → `from app.processing.iir_filter import filtfilt, find_peaks, resample_signal`
- `from scipy.fft import rfft, rfftfreq` → `np.fft.rfft`, `np.fft.rfftfreq`
- All `butter(...)` calls → load pre-computed coefficients from `Config`

The function signatures are unchanged.

---

## Phase 5 — Port the Manager Layer

**Goal:** Keep the recording and streaming logic but remove all Qt dependencies.

### 5.1 — Port `RecordingManager`

Replace `class RecordingManager(QtCore.QObject)` with a plain Python class. Replace
`pyqtSignal` with callback arguments:

```python
# Before:
class RecordingManager(QtCore.QObject):
    overflow_stop_requested = QtCore.pyqtSignal()
    def __init__(self):
        super().__init__()

# After:
class RecordingManager:
    def __init__(self, max_samples=1_000_000, on_overflow=None, on_status=None):
        self.on_overflow = on_overflow
        self.on_status = on_status
```

Replace signal emits with callback calls:
```python
# Before: self.overflow_stop_requested.emit()
# After:  if self.on_overflow: self.on_overflow()
```

The CSV save logic, recording buffer, and file format are unchanged.

### 5.2 — Port `StreamingController`

Replace `QTimer` with Kivy's `Clock.schedule_interval`:

```python
# Before (desktop):
self.timer.start(Config.UPDATE_RATE)  # QTimer, 16ms
self.timer.stop()

# After (Android):
from kivy.clock import Clock
self._clock_event = Clock.schedule_interval(self.update_callback, 1/60)
self._clock_event.cancel()
```

Replace `receiver_thread.isRunning()` (QThread method) with `receiver_thread.is_alive()`
(threading.Thread method).

---

## Phase 6 — Build the UI with Kivy

**Goal:** Create all app screens using Kivy widgets instead of PyQt5.

### 6.1 — Kivy layout basics

| Kivy layout | PyQt5 equivalent |
|---|---|
| `BoxLayout(orientation='vertical')` | `QVBoxLayout` |
| `BoxLayout(orientation='horizontal')` | `QHBoxLayout` |
| `GridLayout(cols=3)` | `QGridLayout` |
| `ScrollView` | `QScrollArea` |
| `Popup` | `QDialog` |

Navigate between screens:
```python
self.manager.current = 'live_data'  # switch to the screen named 'live_data'
```

### 6.2 — `main.py` — Kivy entry point

```python
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from app.ui.screens.selection_screen import SelectionScreen
from app.ui.screens.live_data_screen import LiveDataScreen
from app.ui.screens.data_analysis_screen import DataAnalysisScreen
from app.core.device import SessantaquattroPlus

class OTBApp(App):
    def build(self):
        self.device = SessantaquattroPlus()
        sm = ScreenManager()
        sm.add_widget(SelectionScreen(name='selection'))
        sm.add_widget(LiveDataScreen(name='live_data', device=self.device))
        sm.add_widget(DataAnalysisScreen(name='data_analysis'))
        return sm

    def on_stop(self):
        try:
            self.device.stop_server()
        except Exception:
            pass

if __name__ == '__main__':
    OTBApp().run()
```

### 6.3 — Real-time EMG plot (`emg_plot_widget.py`)

> **Note:** matplotlib and `kivy_matplotlib_widget` were removed because they cannot be
> packaged for Android without significant build complexity. The plot is implemented using
> Kivy's built-in canvas drawing (`Line`, `Color`, `Rectangle`), which requires no
> additional dependencies and renders efficiently on Android.

The `EMGPlotWidget` maintains a rolling buffer of the last N samples and redraws using
Kivy canvas instructions on each update call. Downsampling (every 4th sample by default)
reduces render load on lower-end Android hardware.

### 6.4 — Calibration Popup (`calibration_popup.py`)

Replaces the desktop's `CalibrationDialog`. Two phases controlled by `Clock.schedule_once`:

```python
class CalibrationPopup(Popup):
    def start(self):
        self.open()
        self._start_rest_phase()

    def _start_rest_phase(self):
        # Register callback to collect rest-phase EMG data
        self.on_sample_connect(self._collect_sample)
        self._schedule_progress(REST_DURATION, self._start_mvc_phase)

    def _start_mvc_phase(self, dt=None):
        self._schedule_progress(MVC_DURATION, self._finish)

    def _finish(self, dt=None):
        self.on_sample_disconnect(self._collect_sample)
        # Compute baseline_rms and mvc_rms from buffered samples
        self.on_complete(baseline_rms, threshold, mvc_rms)
```

`Clock.schedule_once(func, delay)` is the direct replacement for `QTimer.singleShot`.

### 6.5 — `DataAnalysisScreen`

Key Kivy widgets:
- `FileChooserListView` — built-in file browser for selecting CSV recordings
- `ScrollView` + `Label` — scrollable text results area
- `GridLayout` — button grid for analysis functions

All feature analysis functions (TKEO, fatigue, bilateral symmetry, centroid shift, spatial
non-uniformity) run in `threading.Thread` workers to avoid blocking the UI, with results
delivered back via `Clock.schedule_once`.

---

## Phase 7 — Package for Android with Buildozer

**Goal:** Produce a working `.apk`.

### 7.1 — `buildozer.spec` — final working configuration

```ini
[app]
title = OTB EMG App
package.name = otbemgapp
package.domain = org.bmeg457

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

# scipy, matplotlib, and kivy_matplotlib_widget have been removed.
# IIR filtering and peak detection are in app/processing/iir_filter.py (numpy only).
# The EMG plot uses Kivy canvas directly.
requirements = python3,kivy==2.3.0,numpy

android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a

orientation = landscape
version = 0.1

[buildozer]
log_level = 2
warn_on_root = 1
```

### 7.2 — Build command

Always run from the symlinked path with `VIRTUAL_ENV=1`:

```bash
cd ~/otb-mobile
VIRTUAL_ENV=1 buildozer android debug 2>&1 | tee ~/build.log
```

**Do not** activate the `.venv` (the Windows desktop venv) before running buildozer.
Buildozer manages its own isolated environment inside `.buildozer/` and never uses the
host `.venv`. If the `.venv` is active, run `deactivate` first.

### 7.3 — Build duration

| Phase | What happens | Approximate time |
|---|---|---|
| First run | Download SDK, NDK (~5 GB) | 10–20 min |
| numpy host build | Compile numpy for host Python (SIMD detection) | 15–30 min (slow in WSL) |
| Recipe compilation | Build kivy, python3, openssl for ARM | 10–20 min |
| APK assembly | Gradle assembleDebug | 5–10 min |
| **Total first run** | | **30–60 min** |
| Subsequent runs | All recipes cached | 2–5 min |

The numpy SIMD detection phase produces many repetitive-looking log lines testing AVX,
AVX512, SSE variants — this is normal, not a loop.

### 7.4 — Clean build (after changing requirements)

```bash
cd ~/otb-mobile
VIRTUAL_ENV=1 buildozer android clean
VIRTUAL_ENV=1 buildozer android debug 2>&1 | tee ~/build.log
```

### 7.5 — Install on phone

```bash
VIRTUAL_ENV=1 buildozer android deploy run
```

### 7.6 — View live logs

```bash
adb logcat | grep -E "python|KIVY|RECEIVER|STREAMING|RECORDING"
```

Every `print()` call in Python code appears here. This is the primary debugging tool
for on-device issues.

---

## Phase 8 — Testing

Work through these tests in order.

### 8.1 — Desktop smoke test

Activate the `.venv` (Windows, with Python 3.12):
```powershell
cd mobile_app
.venv\Scripts\activate
python main.py
```

Verify:
- Selection screen appears with two buttons
- "Live Data" navigates to the live screen
- "Back" returns to selection
- "Data Analysis" shows the file chooser
- No import errors in the terminal

### 8.2 — Processing layer unit test

```bash
python tests/test_processing.py
```
Must print: `Processing pipeline OK`

This test runs the full filter + feature pipeline using `iir_filter.py` (no scipy).

### 8.3 — Networking unit test

```bash
python tests/test_networking.py
```
Must print: `Networking test PASSED`

Uses `unittest.mock` to bypass the WiFi network check and test the TCP handshake locally.

### 8.4 — On-device launch test (no device needed)

Install the APK, launch the app, verify in logcat:
- No `ImportError` or `ModuleNotFoundError`
- Kivy initializes (look for `[KIVY]` lines)
- Selection screen renders without crash

### 8.5 — On-device WiFi test

1. Connect phone to the Sessantaquattro+ WiFi network
2. Launch app → **Start Stream**
3. Check logcat for: `[RECEIVER] First packet processed successfully!`

### 8.6 — Recording test

1. Stream → Calibrate → Record for 10 s → Stop Record
2. Pull the file:
   ```bash
   adb pull /sdcard/Android/data/org.bmeg457.otbemgapp/files/recordings/
   ```
3. Verify the CSV has `Timestamp, Channel_1, ..., Channel_72` headers and numeric data

---

## Known Risks & Resolutions

### scipy cannot build for Android — RESOLVED

**Original risk:** scipy requires Fortran (gfortran) to compile ARM binaries. NDK versions
that include gfortran (r21e and older) are unmaintained and produce broken builds on
modern Ubuntu.

**Resolution implemented:** scipy was removed entirely from the project.
- `app/processing/iir_filter.py` provides pure-numpy `filtfilt`, `find_peaks`, `resample_signal`
- Filter coefficients are pre-computed on desktop with scipy and stored in `config.py`
- `features.py` uses `np.fft.rfft`/`np.fft.rfftfreq` instead of `scipy.fft`
- `buildozer.spec` requirements: `python3,kivy==2.3.0,numpy` (no scipy)

### matplotlib / kivy_matplotlib_widget cannot build for Android — RESOLVED

**Original risk:** matplotlib has C extensions; `kivy_matplotlib_widget` has no p4a recipe.

**Resolution implemented:** Both removed. `emg_plot_widget.py` uses Kivy's built-in canvas
drawing (`Line`, `Color`) with a rolling buffer and 4× downsampling. This is faster on
Android than matplotlib would have been anyway.

### Buildozer `--user` flag error in pipx venv — RESOLVED

**Symptom:** `Cannot perform --user install inside a virtual environment`

**Resolution:** Set `VIRTUAL_ENV=1` before every buildozer command. This causes buildozer
to drop the `--user` flag from all internal pip calls.

### `No module named 'distutils'` — RESOLVED

**Symptom:** Python 3.12 removed `distutils`, causing buildozer to crash on import.

**Resolution:** `pipx inject buildozer setuptools` — setuptools provides the `distutils`
compatibility shim for Python 3.12+.

### Path contains spaces — RESOLVED

**Symptom:** `storage dir path cannot contain spaces` from p4a.

**Resolution:** Project directory renamed to `mobile_app/` (underscore). If the full path
through Windows still has spaces, use a symlink: `ln -s "/mnt/c/.../mobile_app" ~/otb-mobile`

### `pip3 install buildozer` fails — RESOLVED

**Symptom:** `error: externally-managed-environment`

**Resolution:** Use `pipx install buildozer` instead. pipx creates an isolated venv for
buildozer automatically, bypassing the system Python protection.

### Real-time plotting is too slow on Android

**Status:** Not yet tested on device.

**Mitigation strategies (in order of effort):**
1. Increase `DOWNSAMPLE` constant in `emg_plot_widget.py` from 4 to 8 or 16
2. Reduce `DISPLAY_SAMPLES` to shorten the visible time window
3. Only plot channel 0 (average) rather than individual channels

### Android kills the background thread

**Status:** Not yet tested on device.

**Mitigation:** If streaming stops unexpectedly, add `FLAG_KEEP_SCREEN_ON` via pyjnius:
```python
from jnius import autoclass
WindowManager = autoclass('android.view.WindowManager$LayoutParams')
activity = autoclass('org.kivy.android.PythonActivity').mActivity
activity.getWindow().addFlags(WindowManager.FLAG_KEEP_SCREEN_ON)
```
Add `pyjnius` to `requirements` in `buildozer.spec` if this is needed.

---

*End of plan. The APK has been successfully built. Next step: on-device testing (Phase 8.4+).*
