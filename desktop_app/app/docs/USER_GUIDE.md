# OTB-EMG App — User Guide

This guide covers everything needed to operate the OTB-EMG application. No programming knowledge is required.

---

## Table of Contents

1. [What the App Does](#1-what-the-app-does)
2. [Hardware Requirements](#2-hardware-requirements)
3. [Starting the App](#3-starting-the-app)
4. [Live Data Mode](#4-live-data-mode)
   - [Connecting to the Device](#41-connecting-to-the-device)
   - [The Control Bar](#42-the-control-bar)
   - [Streaming](#43-streaming)
   - [Calibration](#44-calibration)
   - [Recording](#45-recording)
   - [Tabs: What Each Shows](#46-tabs-what-each-shows)
5. [Data Analysis Mode](#5-data-analysis-mode)
   - [Loading a Recording](#51-loading-a-recording)
   - [Navigating the Recording](#52-navigating-the-recording)
   - [Signal Processing Controls](#53-signal-processing-controls)
   - [Feature Analysis](#54-feature-analysis)
6. [Session Persistence](#6-session-persistence)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. What the App Does

The OTB-EMG app has two independent operating modes:

- **Live Data Mode**: Streams 64-channel EMG data from the Sessantaquattro+ device over WiFi in real time, displays it across multiple views, and optionally records it to a CSV file.
- **Data Analysis Mode**: Loads previously recorded CSV files and runs post-hoc feature extraction and analysis with interactive visualization. No device is required.

EMG (electromyography) measures the electrical signals produced by muscles. The Sessantaquattro+ device uses an 8×8 grid of 64 electrodes placed on the skin to capture both the timing and spatial distribution of muscle activity.

---

## 2. Hardware Requirements

| Item | Details |
|---|---|
| Device | OTB Sessantaquattro+ HD-sEMG amplifier |
| WiFi | Laptop must connect to the device's WiFi hotspot (SSID provided with device) |
| Electrode array | 8×8 HD-sEMG array, placed and secured on the target muscle |
| Operating system | Windows (tested on Windows 10/11) |

The device creates its own WiFi hotspot. The laptop must be connected to this hotspot (not to the internet) before attempting to stream. The device gateway is at `192.168.1.1`.

---

## 3. Starting the App

Run `OTB-EMG.exe` from the distribution folder. A mode selection window appears with two buttons:

- **Live Data Viewing** — opens the live streaming window
- **Data Analysis** — opens the offline analysis window

Use the **← Back** button in either window to return to this screen at any time.

---

## 4. Live Data Mode

### 4.1 Connecting to the Device

Before connecting:
1. Power on the Sessantaquattro+ device.
2. On the laptop, connect to the device's WiFi network (prefix `192.168.1`).
3. Ensure the electrode array is properly placed on the subject.

In the live data window, click **Connect to Device**. The app opens a TCP server and waits up to 10 seconds for the device to connect. Once connected, the status bar shows "Connected. Ready to stream."

If connection fails:
- Check that the laptop's WiFi shows an IP address starting with `192.168.1`.
- Ensure the device is powered on and the LED is active.
- Check that Windows Firewall is not blocking the app on port 45454.

### 4.2 The Control Bar

| Button | Function |
|---|---|
| Connect to Device | Opens the TCP server and waits for the device |
| Calibrate | Opens the calibration dialog (requires connection) |
| Start Stream / Stop Stream | Starts or stops live data display |
| Start Recording / Stop Recording | Starts or stops saving data to CSV (requires connection) |
| Battery indicator | Shows current device battery level (updated every 30 seconds) |
| Contraction indicator | Green/grey dot that lights up when a contraction is detected |

### 4.3 Streaming

Click **Start Stream** to begin visualizing live EMG data. The plots update at approximately 62 frames per second.

Click **Stop Stream** to pause the display. The device continues to run; pausing only stops data being fed to the plots. Resume by clicking **Start Stream** again.

The **Plot Time** dropdown (top-left) controls how much signal history is visible in the plots: options range from 100 ms to 10 s. A shorter window shows fine temporal detail; a longer window reveals slower patterns.

### 4.4 Calibration

Calibration sets a per-channel reference for resting muscle activity (baseline) and maximum contraction (MVC). It is required for the heatmap to display normalized activation levels.

**Procedure:**

1. Click **Calibrate** (device must be connected and streaming data).
2. **Rest phase** (5 seconds): Instruct the subject to relax completely. Keep the muscle at rest throughout the countdown.
3. **Contraction phase** (5 seconds): Instruct the subject to perform a maximum voluntary contraction (MVC) as consistently as possible. Effort should be maintained throughout.
4. Click OK when complete.

After calibration, the heatmap shows activation as a fraction of MVC. The contraction indicator becomes active.

Calibration data is saved automatically and reloaded the next time the app starts, so recalibration is not required every session.

### 4.5 Recording

Click **Start Recording** to begin saving the raw 64-channel EMG signal to a timestamped CSV file. The file is saved in the `recordings/` folder adjacent to the executable.

The status bar shows the current recording duration. Recording stops automatically if the data buffer fills (approximately 500 seconds at 2000 Hz). Click **Stop Recording** at any time to end and save the file.

Recorded files can be loaded in **Data Analysis Mode** for post-hoc feature extraction.

### 4.6 Tabs: What Each Shows

**All Tracks**

Displays all EMG and auxiliary channels as scrollable waveform plots. Each track can show one or multiple channels simultaneously.

- Use **Select Channels** to choose which channels are displayed on a given track.
- Use **Manage Tracks** to show or hide individual tracks.

**Accessory**

Shows the auxiliary channels (channels 65–72): accelerometer, gyroscope, and other auxiliary signals depending on the device configuration.

**Individual Channels**

Shows a single selected channel's waveform in detail, useful for inspecting signal quality on a specific electrode.

**Features**

Displays live-computed signal features in rolling plots (e.g., RMS, median frequency). Feature computation uses a sliding window of 200 ms, updated at 30 Hz.

**Heatmap**

Displays a real-time 8×8 colour map showing the activation level at each electrode, normalized to the MVC reference from calibration. Colour scale: dark (low/no activation) to bright (near MVC).

This view is only meaningful after calibration. The spatial pattern reveals which muscle regions are active and allows identification of motor unit territory, symmetry, and propagation patterns.

---

## 5. Data Analysis Mode

Data Analysis Mode requires no device. Open it from the mode selection screen.

### 5.1 Loading a Recording

Click **Load File 1** to load a CSV recording. A second file can optionally be loaded with **Load File 2** for bilateral symmetry analysis (left vs. right limb comparison).

After loading, the file name and detected sample rate are displayed. The full recording is plotted immediately.

### 5.2 Navigating the Recording

The time navigation bar appears once a file is loaded:

| Control | Function |
|---|---|
| Slider | Scrubs to any position in the recording (1000 steps across the full duration) |
| `<` / `>` buttons | Move the view window forward or backward by 10% of its current duration |
| Window size input | Sets how many seconds of data are shown at once (0.1–1000 s) |

The default view window is 5 seconds.

### 5.3 Signal Processing Controls

Under the **Data Viewing** tab on the right panel:

| Control | Options | Effect |
|---|---|---|
| Channel 1 / Channel 2 | Channel number | Select which channels to plot |
| Rectify | On/Off | Applies `|x|` to the signal before envelope extraction |
| Envelope | None / RMS / Lowpass | Applies amplitude envelope to the displayed signal |
| RMS Window | Samples (default 50 = 25 ms) | Window length for RMS envelope |
| LP Cutoff | Hz (default 10 Hz) | Cutoff frequency for lowpass envelope |

These controls affect the display only — the underlying data is not modified.

### 5.4 Feature Analysis

Under the **Features** tab on the right panel. Each button runs a specific analysis on the currently loaded file(s) and displays the results in the text panel at the bottom of the window.

| Button | What it computes | Requires |
|---|---|---|
| Activation Timings | Muscle activation onset times and TKEO envelope | File 1 |
| Burst Duration | Number of bursts, mean duration ± std | File 1 |
| Fatigue | RMS increase over time, median frequency decline rate | File 1 |
| Bilateral Symmetry | Sliding-window symmetry index between two channels | Files 1 and 2 |
| Centroid Shift | Spatial shift of the activation centroid over the 8×8 grid | File 1 (64 channels) |
| Spatial Non-Uniformity | Coefficient of variation, Shannon entropy, active electrode fraction | File 1 (64 channels) |

**Activation Timings and Burst Duration** require at least 0.5 seconds of quiet baseline at the start of the recording before any contraction occurs. Results include:
- Onset timestamps (seconds from start of recording)
- Number of detected activations/bursts
- Mean burst duration and standard deviation

**Fatigue** returns:
- Time series of sliding-window RMS
- Time series of median frequency (Hz)
- Time points where RMS fatigue or MF fatigue criteria are met

**Bilateral Symmetry** requires two files. Both are trimmed to their overlapping duration, resampled to a common rate, and the symmetry index `SI = (RMS₁ − RMS₂) / (RMS₁ + RMS₂)` is computed over sliding 250 ms windows. Results report mean SI, std SI, and maximum asymmetry with an assessment label:

| |SI| | Assessment |
|---|---|
| < 0.10 | Good symmetry |
| 0.10–0.25 | Mild asymmetry |
| 0.25–0.50 | Moderate asymmetry |
| > 0.50 | Severe asymmetry |

**Centroid Shift and Spatial Non-Uniformity** require a 64-channel recording. These analyses use the full electrode grid to characterize how the spatial distribution of muscle activity changes over time.

---

## 6. Session Persistence

Calibration data (baseline RMS, activation threshold, and MVC RMS, all per channel) is saved automatically after each calibration to `data/previous_session.csv` in the application folder. This file is loaded automatically at startup, so the heatmap is functional without recalibration between sessions.

To force a fresh calibration (e.g., after repositioning the electrode array), simply click **Calibrate** again. The new calibration overwrites the saved data.

---

## 7. Troubleshooting

**"Not connected to the Sessantaquattro+ WiFi network"**
The laptop's active network IP must start with `192.168.1`. Check WiFi settings and ensure you are connected to the device hotspot, not a router or mobile hotspot.

**"Device did not connect within 10 seconds"**
The device did not reach the laptop's TCP server in time. Confirm the device is powered on, the LED is active, and the WiFi connection is stable. Try clicking **Connect to Device** again.

**Plots are frozen or not updating**
Click **Stop Stream** then **Start Stream**. If streaming was never started, click **Start Stream** first.

**Heatmap is all dark / contraction indicator never lights up**
Calibration is required. Click **Calibrate**, perform the full rest + contraction sequence, and confirm.

**Recording file cannot be found**
Files are saved in the `recordings/` folder adjacent to `OTB-EMG.exe`. Ensure the folder is not write-protected.

**Feature analysis returns no results / "not enough data"**
The recording is too short or the signal does not include enough baseline period. TKEO-based analyses require at least ~0.5 seconds of quiet rest before any contraction. Ensure recordings include a rest period at the start.

**Application crashes on startup**
Ensure `config.json` is present in the same folder as `OTB-EMG.exe`. If missing, copy it from the distribution archive.
