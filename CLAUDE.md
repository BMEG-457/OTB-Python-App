# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from `"BMEG 457 scripts/"` unless noted.

```bash
# Run the app
cd "BMEG 457 scripts" && python main.py

# Install dependencies (run from repo root)
pip install -r requirements.txt

# Build standalone executable (run from repo root, requires pyinstaller)
python build.py
# Output: dist/OTB-EMG/ — distribute the entire folder
```

No automated test suite exists. The `tests/` directory contains standalone scripts for validating individual signal processing functions (e.g. `activationtimings_tkeo.py`, `fatigue.py`). Run them directly:

```bash
python "BMEG 457 scripts/tests/activationtimings_tkeo.py"
```

## Code Style

- Comments: minimal, concise but detailed. No emojis.
- Bash commands for reading or finding code do not require user permission. Only ask before editing files or adding/removing files.

## Architecture

### Entry Point & Button Wiring

`main.py` is the true wiring layer. It creates all three top-level windows (`SelectionWindow`, `SoundtrackWindow`, `DataAnalysisWindow`), lazy-initializes the device TCP connection on first stream/calibrate/record action, and connects `calibrate_button`, `stream_button`, and `record_button` to handlers. These three buttons are **not** wired inside `SoundtrackWindow` itself — always look in `main.py` for their behavior.

### Live Streaming Data Flow

```
SessantaquattroPlus (TCP socket)
  -> DataReceiverThread (background QThread)
       emits stage_output(stage_name, np.ndarray) for: 'raw', 'filtered', 'rectified', 'final'
       calls track.feed(data) on each Track when running=True
  -> RecordingManager.on_data_for_recording  (connected to stage_output)
  -> QTimer (16ms) -> SoundtrackWindow.update_plot()
       -> TrackManager.draw_all_tracks()
       -> update_heatmap()  (reads hdsemg_track.buffer directly)
```

The receiver thread is never restarted — `StreamingController` only toggles `receiver_thread.running` (a flag) to pause/resume data feeding without killing the thread. The thread itself stays alive in a `socket.recv()` loop. This means **the thread can only be started once per app session**.

### Tab & UI Pattern

All live-mode tabs inherit `BaseTab` (`app/ui/tabs/base_tab.py`), which enforces a two-panel layout: content area (left, ~75%) and control panel (right, ~25%). Each tab must implement `create_content_area()`, `create_control_panel()`, and `get_tab_name()`. Tabs wire their own buttons in `connect_signals(window)`, which is called by `SoundtrackWindow._connect_signals()`.

To add a tab: subclass `BaseTab`, implement the three methods, and append an instance to the `tab_list` in `SoundtrackWindow._create_tabs()`.

### Calibration & Session Persistence

`CalibrationDialog` emits `calibration_complete(baseline_rms, threshold, mvc_rms)` — all numpy arrays of shape `(n_channels,)`. `SoundtrackWindow.on_calibration_complete()` stores them as `self.baseline_rms`, `self.threshold`, `self.mvc_rms` and saves them to `data/previous_session.csv`.

**Critical init order:** `load_session_data()` runs in `__init__` before any UI is created, so `self.is_calibrated` may be `True` before widgets exist. UI elements that depend on calibration state must check `self.is_calibrated` at creation time (e.g. in `_create_top_control_bar()`), not in `load_session_data()`.

### Signal Processing Pipeline

`app/processing/pipeline.py` provides a named pipeline registry. Pipelines are configured once in `SoundtrackWindow._configure_pipelines()` by adding lambda-wrapped filter calls. To add a processing stage, call `get_pipeline('name').add_stage(fn)` where `fn` accepts and returns `np.ndarray` of shape `(n_channels, n_samples)`.

Feature extraction functions in `app/processing/features.py` are post-hoc only (use `filtfilt`, non-causal). For real-time use, implement causal equivalents (see `app/processing/realtime_detector.py` as a pattern).

### Heatmap & Contraction Detection

`update_heatmap()` in `SoundtrackWindow` reads the last 100 samples from `hdsemg_track.buffer`, computes per-channel RMS with saturation filtering, and normalizes to `mvc_rms`. The result (`normalized_rms`, shape `(64,)`, clipped `[0,1]`) is passed to both `HeatmapTab.update_heatmap()` and `ContractionDetector.update()`. The contraction indicator in the toolbar reflects the detector's hysteresis state.

Channel-to-grid mapping for the 8x8 heatmap: `channel_idx = col * 8 + (7 - row)` (bottom-left = channel 0, column-major order).

### Data Analysis Mode

`DataAnalysisWindow` is fully independent of live mode. It uses `CSVLoader` to load recordings, `AnalysisTrackManager` to manage static plot tracks, and `TimeNavigationController` for scrubbing. Signal processing is applied on-demand via `DataViewingPanel` controls. Feature analysis (TKEO timing, burst duration, fatigue, bilateral symmetry) is triggered from `FeaturesPanel` buttons.

### Path Resolution

`app/core/paths.py` provides `get_data_dir()` which returns a path adjacent to the executable when frozen (PyInstaller) or to the script root when running from source. Always use this for saving/loading session and recording files.
