# OTB-Python-App

A PyQt5-based desktop application for real-time High-Density Surface Electromyography (HD-sEMG) signal acquisition, visualization, and analysis. Designed for the OTBioelettronica Sessantaquattro+ device (64-channel EMG system).

---

## Repository Layout

```
OTB-Python-App/
├── desktop_app/         Main application (Python + PyQt5, Windows)
├── exploratory testing/ Standalone signal processing and analysis scripts
├── OTB files/           Original OTB device reference scripts
└── requirements.txt     Python dependencies for the desktop app
```

---

## Desktop App

### Features

**Live Data Mode**
- 64-channel real-time EMG streaming from the Sessantaquattro+ over WiFi
- Six visualization tabs: All Tracks, Accessory channels, HD-sEMG, Heatmap, Individual Channels, Features
- 8×8 heatmap of muscle activation normalized to MVC
- Live contraction detection with hysteresis
- Battery level polling via HTTP (independent of data stream)
- Configurable plot time window (100 ms – 10 s)
- CSV recording with automatic timestamping (1 M sample limit)

**Calibration**
- Two-phase protocol: 5 s rest → 5 s maximum voluntary contraction
- Per-channel baseline RMS, activation threshold (mean + 3σ), and MVC reference (99th percentile)
- Automatic bad-channel detection and spatial interpolation
- Calibration persisted to disk and restored at next launch

**Data Analysis Mode** (no device required)
- Load one or two CSV recordings
- Time navigation: slider, step buttons, configurable window size
- Signal processing controls: rectification, RMS envelope, lowpass envelope
- Six feature analyses:
  - TKEO activation timing (onset detection with backtracking)
  - Burst duration (count, mean ± std)
  - Fatigue (RMS increase + median frequency decline)
  - Bilateral symmetry index (requires two files)
  - HD-EMG centroid shift over time (requires 64-channel recording)
  - Spatial non-uniformity (CV, Shannon entropy, active electrode fraction)

### Quick Start

**From source:**

```bash
pip install -r requirements.txt
cd desktop_app
python main.py
```

**From the built executable:**

Run `dist/OTB-EMG/OTB-EMG.exe`. `config.json` must be present in the same folder as the executable.

**Emulator mode** (no hardware required, for UI development):

```bash
set SESSANTAQUATTRO_EMULATOR=1
cd desktop_app
python main.py
```

### Configuration

All tunable parameters are in `desktop_app/config.json`. Edit this file to change filter frequencies, calibration durations, feature thresholds, UI settings, and more. No source code changes are needed for parameter tuning. See [DESIGN_RATIONALE.md](desktop_app/app/docs/DESIGN_RATIONALE.md) for the reasoning behind each value.

### Building a Standalone Executable

Requires PyInstaller (`pip install pyinstaller`). Run from `desktop_app/`:

```bash
cd desktop_app
python build.py
```

Output: `desktop_app/dist/OTB-EMG/`. Distribute the entire folder. Copy `config.json` alongside `OTB-EMG.exe` before distributing.

### Testing

Unit tests are in `desktop_app/tests/`. They cover the non-UI modules: signal processing filters, the pipeline registry, contraction detection, CSV loading, device command encoding, time navigation, and all feature extraction functions. No hardware or display is required.

```bash
cd desktop_app
python -m pytest tests/ -v
```

### CI/CD

A GitHub Actions workflow (`.github/workflows/ci.yml`) runs the test suite automatically on every push and pull request to `main`.

The workflow:
1. Runs on `ubuntu-latest`
2. Installs system libraries required by PyQt5 (`libgl1`, `libglib2.0-0`, `libxcb-xinerama0`)
3. Installs Python dependencies from `requirements.txt`
4. Runs `pytest` with `QT_QPA_PLATFORM=offscreen` so PyQt5 works without a display

Status is visible in the **Actions** tab of the GitHub repository.

| Test file | Module under test |
|---|---|
| `test_filters.py` | `app/processing/filters` — bandpass, notch, rectify |
| `test_pipeline.py` | `app/processing/pipeline` — stage chaining, named registry |
| `test_realtime_detector.py` | `app/processing/realtime_detector` — hysteresis ON/OFF logic |
| `test_csv_loader.py` | `app/data/csv_loader` — parsing, shape, sample rate estimation |
| `test_device.py` | `app/core/device` — channel count mapping, frequency mapping, command bit layout |
| `test_time_navigation.py` | `app/managers/time_navigation_controller` — seek, scroll, zoom, clamping |
| `test_features.py` | `app/processing/features` — RMS/MAV/IEMG, TKEO timing, burst duration, bilateral symmetry, fatigue, centroid shift, spatial non-uniformity |

### Documentation

Full documentation is in `desktop_app/app/docs/`:

| Document | Contents |
|---|---|
| [USER_GUIDE.md](desktop_app/app/docs/USER_GUIDE.md) | Hardware setup, connecting, calibration, recording, all tabs, data analysis, troubleshooting |
| [DEVELOPER_GUIDE.md](desktop_app/app/docs/DEVELOPER_GUIDE.md) | Architecture, TCP protocol, live pipeline, signal processing, UI/tab patterns, build system |
| [DESIGN_RATIONALE.md](desktop_app/app/docs/DESIGN_RATIONALE.md) | Justification and literature sources for all constants, thresholds, and algorithm choices |

---

## Dependencies

| Library | Version | Purpose |
|---|---|---|
| PyQt5 | 5.15.11 | UI framework and threading |
| pyqtgraph | 0.13.7 | Real-time plot rendering |
| numpy | 2.3.5 | Array operations throughout the pipeline |
| scipy | 1.16.3 | Filter design, FFT, resampling, peak finding |

Install: `pip install -r requirements.txt`

---

## Hardware

- **OTBioelettronica Sessantaquattro+** — 64-channel HD-sEMG amplifier
- Sampling rate: 500 / 1000 / 2000 / 4000 Hz (default: 2000 Hz)
- Communication: TCP over WiFi; device connects to laptop as TCP client on port 45454
- The laptop must be connected to the device's WiFi hotspot before streaming

---

## Known Limitations

- Maximum recording duration: ~500 s at 2000 Hz (1 M sample limit, 64 channels)
- Heatmap and spatial analyses assume the standard 8×8 electrode grid in column-major, bottom-left origin layout
- The receiver thread cannot be restarted within a session; a full app restart is required to reconnect after the socket is closed

---

## Project Context

Developed as part of BMEG 457 coursework.
