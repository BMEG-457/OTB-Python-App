# Android Port Plan — OTB EMG App

## Table of Contents
1. [What This Plan Is](#what-this-plan-is)
2. [Key Concepts for Beginners](#key-concepts-for-beginners)
3. [What Gets Reused vs. Rewritten](#what-gets-reused-vs-rewritten)
4. [Architecture of the Android App](#architecture-of-the-android-app)
5. [Phase 1 — Development Environment Setup](#phase-1--development-environment-setup)
6. [Phase 2 — Project Structure](#phase-2--project-structure)
7. [Phase 3 — Port the Core Layer](#phase-3--port-the-core-layer)
8. [Phase 4 — Copy the Processing Layer](#phase-4--copy-the-processing-layer)
9. [Phase 5 — Port the Manager Layer](#phase-5--port-the-manager-layer)
10. [Phase 6 — Build the UI with Kivy](#phase-6--build-the-ui-with-kivy)
11. [Phase 7 — Package for Android with Buildozer](#phase-7--package-for-android-with-buildozer)
12. [Phase 8 — Testing](#phase-8--testing)
13. [Known Risks & Fallback Strategies](#known-risks--fallback-strategies)

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

Before diving in, here is a plain-language explanation of every tool and term used in this plan.

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

Understanding what to keep prevents wasted work.

### Keep unchanged (platform-agnostic Python)

| File | Why it can stay |
|------|----------------|
| `app/processing/filters.py` | Pure numpy/scipy math, no UI |
| `app/processing/features.py` | Pure numpy/scipy math, no UI |
| `app/processing/pipeline.py` | Pure Python, no UI |
| `app/processing/transforms.py` | Pure numpy, no UI |
| `app/core/device.py` | Standard Python sockets (minor changes needed — see Phase 3) |

### Must be rewritten (desktop-only code)

| File | Reason it must change | Android replacement |
|------|----------------------|---------------------|
| `main.py` | PyQt5 `QApplication` entry point | Kivy `App` entry point |
| `app/ui/windows/main_window.py` | PyQt5 widgets and pyqtgraph plots | Kivy screens + matplotlib |
| `app/ui/windows/data_analysis_window.py` | PyQt5 widgets | Kivy screen |
| `app/ui/tabs/tab_implementations.py` | PyQt5 + pyqtgraph tabs | Kivy tab panels |
| `app/ui/dialogs/dialogs.py` | PyQt5 dialogs | Kivy Popup widgets |
| `app/data/data_receiver.py` | Uses `QThread` and `pyqtSignal` | Uses `threading.Thread` + callbacks |
| `app/managers/recording_manager.py` | Uses `QObject`/`pyqtSignal` | Plain Python class with callbacks |
| `app/managers/streaming_controller.py` | Uses PyQt5 `QTimer` | Uses Kivy `Clock` |
| `app/managers/track_manager.py` | Uses PyQt5 | Plain Python |
| `app/core/track.py` | Tied to pyqtgraph plot objects | Kivy canvas or matplotlib axes |

---

## Architecture of the Android App

Here is how the layers fit together in the Android version.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Kivy UI Layer                           │
│  SelectionScreen | LiveDataScreen | DataAnalysisScreen          │
│  (uses Kivy widgets, matplotlib plots, Kivy Popups)             │
└────────────────────────────┬────────────────────────────────────┘
                             │ calls / callbacks
┌────────────────────────────▼────────────────────────────────────┐
│                        Manager Layer                            │
│  RecordingManager | StreamingController | TrackManager          │
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
│  (pure numpy/scipy — unchanged from desktop)                    │
└─────────────────────────────────────────────────────────────────┘
```

Data flows upward: the device sends raw bytes → DataReceiverThread decodes and processes them
→ calls a callback → managers update state → Kivy UI re-draws the plot.

---

## Phase 1 — Development Environment Setup

**Goal:** Get a working Android build environment on your Windows machine.

### Step 1.1 — Install WSL2
WSL2 gives you a real Linux environment inside Windows.

1. Open PowerShell as Administrator and run:
   ```
   wsl --install
   ```
2. Restart your computer when prompted.
3. On first launch, WSL will ask you to create a Linux username and password. This is separate
   from your Windows account — pick anything you like.
4. You now have an Ubuntu terminal. All following commands run inside this Ubuntu terminal
   unless stated otherwise.

### Step 1.2 — Install Python and system dependencies in WSL
Inside the Ubuntu terminal:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git \
    zip unzip openjdk-17-jdk autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake \
    libffi-dev libssl-dev
```

### Step 1.3 — Install Buildozer
```bash
pip3 install --user buildozer
```

Close and reopen your WSL terminal so the `buildozer` command is found in your PATH.

### Step 1.4 — Install the Android SDK and NDK (automated)
Buildozer downloads the Android SDK and NDK automatically on first build. You don't need to
install them manually. The first build will take 20–40 minutes and requires an internet
connection.

### Step 1.5 — Verify Kivy runs on desktop
Before building for Android, confirm Kivy works on your desktop. In WSL (or Windows directly
using your regular Python):
```bash
pip install kivy
python -c "import kivy; print(kivy.__version__)"
```
A version number means Kivy installed correctly.

### Step 1.6 — Enable USB debugging on your Android phone
1. Go to **Settings → About Phone** and tap **Build Number** seven times. This unlocks
   developer mode.
2. Go to **Settings → Developer Options** and turn on **USB Debugging**.
3. Connect your phone via USB. When prompted on the phone, tap "Allow" to trust the computer.

### Step 1.7 — Install ADB (Android Debug Bridge)
ADB is a command-line tool to install and debug apps on your phone.
```bash
sudo apt install adb
adb devices   # should list your phone's serial number
```

---

## Phase 2 — Project Structure

**Goal:** Create a clean directory layout for the Android app.

Create this folder structure inside `mobile app/`:

```
mobile app/
├── PLAN.md                    ← this file
├── buildozer.spec             ← Buildozer configuration (created in Phase 7)
├── main.py                    ← Kivy app entry point
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          ← same constants, no PyQt5
│   │   └── device.py          ← ported from desktop (Phase 3)
│   ├── data/
│   │   ├── __init__.py
│   │   └── data_receiver.py   ← ported from desktop (Phase 3)
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── filters.py         ← copied verbatim (Phase 4)
│   │   ├── features.py        ← copied verbatim (Phase 4)
│   │   ├── pipeline.py        ← copied verbatim (Phase 4)
│   │   └── transforms.py      ← copied verbatim (Phase 4)
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
│           ├── emg_plot_widget.py     ← real-time plot
│           └── calibration_popup.py   ← calibration dialog
└── assets/                    ← icons, fonts (optional)
```

Copy all the `__init__.py` files from the desktop app as blank files.
Copy `app/core/paths.py` and update it for Android paths (see Phase 3).

---

## Phase 3 — Port the Core Layer

**Goal:** Make the device communication and data receiver work without PyQt5.

### 3.1 — Port `app/core/device.py`

The desktop version calls `sys.exit(1)` on connection errors (acceptable for a desktop app,
but on Android it would crash the whole app silently). The Android version should raise
exceptions instead so the UI can show a proper error message.

**Changes needed:**
- Remove all `sys.exit(1)` calls. Replace with `raise ConnectionError("message")`.
- The rest of the socket logic is unchanged — Python's `socket` module works on Android.

Conceptually, `start_server()` becomes:
```
start_server():
    if not connected to device WiFi network:
        raise ConnectionError("Not on device network")
    create TCP socket, bind to port 45454, wait for device to connect
    if device doesn't connect within 10 seconds:
        raise ConnectionError("Device did not connect in time")
```

### 3.2 — Port `app/data/data_receiver.py`

The desktop version is a `QThread` (PyQt5 background thread). The Android version is a
`threading.Thread` (standard Python background thread).

The key difference: instead of `pyqtSignal`, the receiver calls Python functions ("callbacks")
directly. A callback is just a function you pass in as a parameter.

**Pattern to follow:**

Desktop version (PyQt5):
```python
class DataReceiverThread(QThread):
    data_received = pyqtSignal(np.ndarray)  # signal

    def run(self):
        ...
        self.data_received.emit(processed_data)  # emit
```

Android version (threading.Thread):
```python
import threading

class DataReceiverThread(threading.Thread):
    def __init__(self, device, client_socket, tracks, on_data=None, on_error=None):
        super().__init__(daemon=True)
        self.on_data = on_data      # function to call with processed data
        self.on_error = on_error    # function to call on error
        self.running = False
        ...

    def run(self):
        ...
        if self.on_data:
            self.on_data('raw', reshaped_data)      # callback instead of emit
        ...
        if self.on_error:
            self.on_error("Connection closed")
```

The background thread runs in a separate Python thread. To update the Kivy UI from a
background thread, wrap UI updates with `Clock.schedule_once()`:
```python
from kivy.clock import Clock

# Inside the callback that the UI registers:
def my_on_data(stage, data):
    def update_ui(dt):
        my_kivy_widget.update_plot(data)
    Clock.schedule_once(update_ui, 0)  # 0 = run ASAP on the UI thread
```

This `Clock.schedule_once` pattern is the Kivy equivalent of Qt's thread-safe signal
delivery. It is the most important pattern to understand in the port.

### 3.3 — Port `app/core/paths.py`

On Android, apps cannot write to arbitrary directories. They must use the app's private
storage directory. Update `paths.py` to detect the platform:

```python
import os
from kivy.app import App

def get_data_dir():
    # On Android, App().user_data_dir returns the private app storage path.
    # On desktop, fall back to the existing behavior.
    try:
        return App.get_running_app().user_data_dir
    except Exception:
        return os.path.join(os.path.expanduser("~"), "OTB_EMG_Data")

def get_recordings_dir():
    return os.path.join(get_data_dir(), "recordings")
```

---

## Phase 4 — Copy the Processing Layer

**Goal:** Bring all signal-processing code across unchanged.

Copy these four files verbatim from `BMEG 457 scripts/app/processing/` into
`mobile app/app/processing/`:

- `filters.py`
- `features.py`
- `pipeline.py`
- `transforms.py`

No code changes are needed. These files contain only numpy/scipy math and are completely
platform-agnostic. Verify that the imports at the top of each file only reference `numpy`,
`scipy`, and the standard library — if so, they will work on Android without modification.

**Important:** scipy's `butter`, `filtfilt`, `find_peaks`, and FFT functions are all included
in Buildozer's `scipy` recipe for Android. They are available. See Phase 7 for how to declare
scipy as a dependency.

---

## Phase 5 — Port the Manager Layer

**Goal:** Keep the recording and streaming logic but remove all Qt dependencies.

### 5.1 — Port `RecordingManager`

The desktop version inherits from `QObject` (so it can use `pyqtSignal`). The Android version
is a plain Python class.

**Changes needed:**
- Remove `from PyQt5 import QtCore` and `class RecordingManager(QtCore.QObject)`.
- Replace `class RecordingManager(QtCore.QObject):` with `class RecordingManager:`.
- Replace the two `pyqtSignal` declarations with plain callable attributes:
  ```python
  # Desktop: overflow_stop_requested = QtCore.pyqtSignal()
  # Android:
  def __init__(self, max_samples=1_000_000, on_overflow=None, on_status=None):
      self.on_overflow = on_overflow   # function to call on overflow
      self.on_status = on_status       # function to call with status strings
  ```
- Replace `self.overflow_stop_requested.emit()` with `if self.on_overflow: self.on_overflow()`.
- Replace `self.status_update.emit(msg)` with `if self.on_status: self.on_status(msg)`.
- The CSV save logic and the recording buffer logic are unchanged — copy them as-is.
- Update the import for `get_recordings_dir` to point to the new `app/core/paths.py`.

### 5.2 — Port `StreamingController`

The desktop version uses a `QTimer` to call the UI update loop at 16 ms intervals. On Android,
use Kivy's `Clock.schedule_interval` instead.

**Conceptual change:**
```python
# Desktop:
self.update_timer = QtCore.QTimer()
self.update_timer.timeout.connect(self.update_callback)
self.update_timer.start(16)  # 16ms = ~60fps

# Android (Kivy Clock):
from kivy.clock import Clock
self._clock_event = Clock.schedule_interval(self.update_callback, 1/60)

# To stop:
self._clock_event.cancel()
```

Replace the QTimer import and usage. The rest of the start/stop/pause lifecycle logic
is unchanged.

---

## Phase 6 — Build the UI with Kivy

**Goal:** Create all app screens using Kivy widgets instead of PyQt5.

This is the largest phase. Kivy apps are built around a `ScreenManager` that holds multiple
`Screen` objects — one per "page" of the app.

### 6.1 — Kivy basics you need to know

A Kivy widget is positioned using layouts:
- `BoxLayout`: stacks widgets vertically or horizontally (like `QVBoxLayout`/`QHBoxLayout`)
- `GridLayout`: grid of widgets (like `QGridLayout`)
- `FloatLayout`: free positioning by percentage coordinates

A Kivy `Screen` is like a PyQt5 `QWidget` window. You navigate between screens:
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

if __name__ == '__main__':
    OTBApp().run()
```

### 6.3 — `SelectionScreen`

Equivalent to the desktop's `SelectionWindow`. Two buttons: "Live Data" and "Data Analysis".

```python
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

class SelectionScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=40, spacing=20)
        layout.add_widget(Label(text='Select Mode', font_size=32))

        btn_live = Button(text='Live Data Viewing', size_hint=(1, 0.3))
        btn_live.bind(on_press=self.go_live)
        layout.add_widget(btn_live)

        btn_analysis = Button(text='Data Analysis', size_hint=(1, 0.3))
        btn_analysis.bind(on_press=self.go_analysis)
        layout.add_widget(btn_analysis)

        self.add_widget(layout)

    def go_live(self, instance):
        self.manager.current = 'live_data'

    def go_analysis(self, instance):
        self.manager.current = 'data_analysis'
```

### 6.4 — `LiveDataScreen`

This is the most complex screen. It replaces `SoundtrackWindow`. It contains:
- A top bar: Back, Calibrate, Stream, Record buttons, and a contraction indicator label
- A real-time EMG plot
- A status label

**Top bar layout:**
```python
top_bar = BoxLayout(orientation='horizontal', size_hint=(1, 0.1))
top_bar.add_widget(Button(text='← Back', on_press=self.go_back))
top_bar.add_widget(Button(text='Calibrate', on_press=self.calibrate))
self.stream_btn = Button(text='Start Stream', on_press=self.toggle_stream)
top_bar.add_widget(self.stream_btn)
self.record_btn = Button(text='Start Record', on_press=self.toggle_record)
top_bar.add_widget(self.record_btn)
self.contraction_label = Label(text='No Contraction', color=(1, 0, 0, 1))
top_bar.add_widget(self.contraction_label)
```

**Real-time plot with matplotlib:**

Install `kivy_matplotlib_backend` for Kivy + matplotlib integration:
```bash
pip install kivy_matplotlib_backend matplotlib
```

In your buildozer.spec, add `matplotlib` and `kivy_matplotlib_backend` to `requirements`.

```python
import matplotlib.pyplot as plt
from kivy_matplotlib_backend.backend_kivy import FigureCanvasKivy

class LiveDataScreen(Screen):
    def __init__(self, device, **kwargs):
        super().__init__(**kwargs)
        self.device = device
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasKivy(self.fig)
        self.line, = self.ax.plot([], [])
        ...
        layout.add_widget(self.canvas)
```

To update the plot on each data packet:
```python
def update_plot(self, new_data):
    # new_data is a numpy array, shape (channels, samples)
    # Show channel 0 for simplicity
    y = new_data[0]
    x = range(len(y))
    self.line.set_data(x, y)
    self.ax.relim()
    self.ax.autoscale_view()
    self.canvas.draw()
```

Call this from the data callback:
```python
def on_data_received(self, stage, data):
    if stage == 'final':
        def do_update(dt):
            self.update_plot(data)
        Clock.schedule_once(do_update, 0)
```

### 6.5 — Calibration Popup

Replace the desktop's `CalibrationDialog` with a Kivy `Popup`:

```python
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock

class CalibrationPopup(Popup):
    def __init__(self, on_complete, **kwargs):
        super().__init__(**kwargs)
        self.title = 'Calibration'
        self.size_hint = (0.8, 0.5)
        self.on_complete = on_complete
        self.status_label = Label(text='Get ready for rest...')
        content = BoxLayout(orientation='vertical')
        content.add_widget(self.status_label)
        self.content = content

    def start(self):
        self.open()
        # Phase 1: rest for 3 seconds
        self.status_label.text = 'Stay relaxed (3 seconds)...'
        Clock.schedule_once(self._start_mvc, 3)

    def _start_mvc(self, dt):
        # Phase 2: MVC for 3 seconds
        self.status_label.text = 'Maximum contraction now! (3 seconds)'
        Clock.schedule_once(self._finish, 3)

    def _finish(self, dt):
        self.dismiss()
        self.on_complete()
```

The Kivy `Clock.schedule_once(func, delay)` replaces the desktop's `QTimer.singleShot`.

### 6.6 — `DataAnalysisScreen`

This screen replaces `DataAnalysisWindow`. It allows loading CSV files saved by the
recording manager and running post-session analysis (TKEO, fatigue, bilateral symmetry).

Key Kivy widgets to use:
- `FileChooserListView` — built-in file browser widget for selecting CSV files
- `ScrollView` + `GridLayout` — for displaying analysis results as text
- `Button` — to trigger each analysis function

Bind each analysis button to call the corresponding function from `features.py` and display
results in a label or a matplotlib plot.

---

## Phase 7 — Package for Android with Buildozer

**Goal:** Create the `buildozer.spec` config file and produce a working `.apk`.

### 7.1 — Initialize Buildozer

In your WSL terminal, navigate to the `mobile app/` directory:
```bash
cd /mnt/c/Users/Nicholas\ Santoso/Documents/Code/Python/OTB-Python-App/mobile\ app
buildozer init
```

This creates `buildozer.spec`. Open it and edit these key fields:

### 7.2 — `buildozer.spec` settings

```ini
# App identity
title = OTB EMG App
package.name = otbemgapp
package.domain = org.bmeg457

# Entry point
source.dir = .
source.include_exts = py,png,jpg,kv,atlas

# Dependencies — critical section
requirements = python3,kivy==2.3.0,numpy,scipy,matplotlib,kivy_matplotlib_backend

# Android permissions — the app needs internet access for the TCP socket
android.permissions = INTERNET

# Target Android version
android.api = 33
android.minapi = 21

# Architecture (include both for compatibility)
android.archs = arm64-v8a, armeabi-v7a

# Orientation
orientation = landscape
```

### 7.3 — First build

```bash
buildozer -v android debug
```

The `-v` flag gives verbose output so you can see what is happening. On the first run,
Buildozer downloads the Android SDK and NDK (several gigabytes). This is normal and only
happens once.

If the build succeeds, the `.apk` file will be in `mobile app/bin/`.

### 7.4 — Install on phone

With your phone connected via USB:
```bash
buildozer android deploy run
```

This installs and launches the app on your phone.

### 7.5 — Viewing logs

To see print statements and errors from the running app:
```bash
adb logcat | grep python
```

This is your main debugging tool. Every `print()` call in Python code appears here.

---

## Phase 8 — Testing

Work through these tests in order. Fix any failures before moving to the next step.

### 8.1 — Desktop smoke test (before building for Android)

Run the Kivy app on your desktop first. It is much faster to debug on desktop than on a phone.

```bash
cd "mobile app"
python main.py
```

Verify:
- The selection screen appears with two buttons
- Pressing "Live Data" shows the live data screen
- Pressing "Back" returns to selection
- The calibration popup opens and closes correctly

### 8.2 — Processing layer unit test

Verify that the copied processing code works before touching the UI at all. Create a file
`mobile app/tests/test_processing.py`:

```python
import numpy as np
from app.processing.filters import butter_bandpass, notch, rectify
from app.processing.features import rms, mav

# Simulate 72 channels, 128 samples at 2048 Hz
fake_data = np.random.randn(72, 128).astype(np.float32)

filtered = butter_bandpass(fake_data, 20, 450, 2048)
notched = notch(filtered, 60, 2048)
rect = rectify(notched)
rms_val = rms(rect)

print("Processing pipeline OK")
print(f"RMS shape: {rms_val.shape}")  # should be (72, 1)
```

Run: `python tests/test_processing.py`. If it prints "OK", the processing layer is fine.

### 8.3 — Networking test (before involving the device)

Test that the TCP server can accept a connection using a fake client. Create
`mobile app/tests/test_networking.py`:

```python
import threading, socket, time
from app.core.device import SessantaquattroPlus

device = SessantaquattroPlus()

def fake_device():
    time.sleep(0.5)  # let the server start first
    s = socket.socket()
    s.connect(('127.0.0.1', 45454))
    print("Fake device connected")
    s.close()

threading.Thread(target=fake_device, daemon=True).start()
device.start_server(connection_timeout=5)
print("Server accepted connection OK")
```

### 8.4 — On-device WiFi test

With the actual Sessantaquattro+ powered on:
1. Connect the Android phone to the device's WiFi network (same as you would for the desktop).
2. Launch the app and press "Start Stream".
3. Confirm the phone receives data by checking `adb logcat` for the
   `[RECEIVER] First packet processed successfully!` log line.

### 8.5 — Recording test

1. Start streaming.
2. Press "Start Record", wait 10 seconds, press "Stop Record".
3. Navigate to the phone's private storage using a file manager app, or pull the file with:
   ```bash
   adb pull /sdcard/Android/data/org.bmeg457.otbemgapp/files/recordings/
   ```
4. Open the CSV in Excel or Python to verify it has correct column headers and numeric data.

---

## Known Risks & Fallback Strategies

### Risk: scipy fails to build for Android

scipy has C and Fortran extensions that Buildozer must compile for ARM. This sometimes fails
due to missing compilers or version incompatibilities.

**Fallback:** Implement the two filter functions (`butter_bandpass` and `notch`) in pure numpy
using the bilinear transform. This is more code but removes the scipy dependency entirely.
The feature functions (`compute_tkeo_activation_timing`, etc.) can remain scipy-based and be
used only in the data analysis screen where they are not called in real time.

### Risk: Real-time plotting is too slow on Android

Android phones are slower than desktop computers. Drawing 72 channels at 60 fps may cause
lag.

**Mitigation strategies (in order of effort):**
1. Only plot the average of all channels, not each channel individually.
2. Downsample the display: only send every 4th sample to the plot.
3. Reduce the number of channels shown (e.g., a slider to select how many channels are
   displayed).
4. Replace matplotlib with direct Kivy canvas drawing, which is faster but harder to code.

### Risk: Android kills the background thread

Android can kill background threads in apps it considers idle. Use a Kivy foreground service
or ensure the screen stays on during streaming:
```python
from android.permissions import request_permissions, Permission
from jnius import autoclass

# Prevent screen from sleeping during streaming
WindowManager = autoclass('android.view.WindowManager$LayoutParams')
activity = autoclass('org.kivy.android.PythonActivity').mActivity
activity.getWindow().addFlags(WindowManager.FLAG_KEEP_SCREEN_ON)
```

This requires `pyjnius` in your buildozer.spec requirements.

### Risk: TCP server port 45454 is blocked by Android firewall

Android generally allows apps to bind to ports above 1024 without root. Port 45454 should
work. If it doesn't, try connecting the phone to the device's WiFi network and checking
whether a firewall app is active.

### Risk: File storage path differs from expected

`App.get_running_app().user_data_dir` is the safest path on Android. Do not use hardcoded
paths like `/sdcard/` as they require extra permissions in Android 10+.

---

*End of plan. Each phase builds on the previous one — complete them in order.*
