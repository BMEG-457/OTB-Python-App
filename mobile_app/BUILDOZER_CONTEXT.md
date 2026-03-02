# Mobile App Build Context

## Environment

- **Platform:** WSL2 (Ubuntu) on Windows 11
- **Project path in WSL:** `/mnt/c/Users/Nicholas/Documents/Code/Python/BMEG_457/OTB-mobile/OTB-Python-App/mobile_app/`
- **Symlink (no spaces):** `~/otb-mobile` → project path (required — p4a rejects paths with spaces)
- **Build command:** `cd ~/otb-mobile && VIRTUAL_ENV=1 LEGACY_NDK=~/android-ndk-r21e buildozer android debug`

---

## Buildozer Setup (WSL)

### Installed tools

```bash
sudo apt install -y python3 python3-pip python3-venv git \
    zip unzip openjdk-17-jdk autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake \
    libffi-dev libssl-dev pipx cython3

pipx ensurepath && source ~/.bashrc
pipx install buildozer
pipx inject buildozer setuptools appdirs colorama jinja2 "sh>=1.10,<2.0" build toml packaging
```

### Required env vars

| Variable | Value | Reason |
|---|---|---|
| `VIRTUAL_ENV=1` | any non-empty string | Stops buildozer from passing `--user` to pip inside its venv (see android.py line 720) |
| `LEGACY_NDK=~/android-ndk-r21e` | path to NDK r21e | scipy/numpy need gfortran; r25b dropped it. **Now removed from requirements — no longer needed.** |

### NDK r21e (kept on disk, not currently needed)

```bash
cd ~ && wget https://dl.google.com/android/repository/android-ndk-r21e-linux-x86_64.zip
unzip android-ndk-r21e-linux-x86_64.zip
```

---

## Errors Encountered & Fixes

| Error | Fix |
|---|---|
| `externally-managed-environment` on `pip3 install buildozer` | Use `pipx install buildozer` |
| `No module named 'distutils'` (Python 3.12 removed it) | `pipx inject buildozer setuptools` |
| `# Cython not found` | `pipx inject buildozer cython` (also `sudo apt install cython3` for system Python) |
| `Cannot perform --user install` in pipx venv | `pipx inject buildozer appdirs colorama jinja2 ...` + set `VIRTUAL_ENV=1` |
| `storage dir path cannot contain spaces` | Symlink project to `~/otb-mobile` (no spaces in path) |
| `LEGACY_NDK not found` / gfortran missing | Download NDK r21e; **now moot — scipy removed** |

### The `--user` flag patch (for reference)

The flag is at line 720 of `android.py` in the buildozer pipx venv:
```python
options = ["--user"]
if "VIRTUAL_ENV" in os.environ or "CONDA_PREFIX" in os.environ:
    options = []
```
Setting `VIRTUAL_ENV=1` makes buildozer drop the `--user` flag automatically — no source patching needed.

---

## Dependency Removal (scipy / matplotlib / kivy_matplotlib_widget)

These were removed to avoid the Android gfortran/NDK requirement.

### `buildozer.spec` requirements (after)

```ini
requirements = python3,kivy==2.3.0,numpy
```

### New files created

| File | Purpose |
|---|---|
| `app/processing/iir_filter.py` | Pure-numpy `lfilter`, `filtfilt`, `find_peaks`, `resample_signal` |
| `scripts/compute_filter_coeffs.py` | Offline script to regenerate filter coefficients via scipy |

### Files changed

| File | What changed |
|---|---|
| `app/core/config.py` | Expanded: all tunable params + pre-computed Butterworth b/a arrays |
| `app/processing/filters.py` | Removed scipy; uses config coefficients + `iir_filter.filtfilt` |
| `app/processing/features.py` | Removed `scipy.signal` and `scipy.fft`; uses `iir_filter` + `np.fft` + config |
| `app/ui/widgets/emg_plot_widget.py` | Replaced matplotlib + `kivy_matplotlib_widget` with pure Kivy canvas |
| `app/ui/widgets/calibration_popup.py` | Durations and threshold fraction now read from config |
| `app/ui/screens/live_data_screen.py` | Pipeline setup and device command params now read from config |

### Filter coefficient design

Pre-computed at **DEVICE_SAMPLE_RATE = 2000 Hz** (FSAMP=2, MODE=0):

| Config key | Filter | Use |
|---|---|---|
| `BANDPASS_4_B/A` | butter(4, [20, 450] Hz, band) | Live pipeline + post-session analysis |
| `BANDPASS_1_B/A` | butter(1, [20, 450] Hz, band) | Short-data fallback in `butter_bandpass` |
| `LOWPASS_10_4_B/A` | butter(4, 10 Hz, low) | TKEO envelope smoothing |
| `NOTCH_60_B/A` | butter(2, 60 Hz notch, Q=30) | Power-line notch in live pipeline |

To regenerate for a different sample rate:
```bash
python scripts/compute_filter_coeffs.py --fs 4000
# paste output into config.py FILTER COEFFICIENTS section
```

### Key design notes

- `iir_filter.filtfilt` uses reflect padding (length = `3 * max(len(a), len(b))`), matching scipy's default
- `iir_filter.find_peaks` returns `(indices, {})` matching scipy's interface
- `iir_filter.resample_signal` uses linear interpolation (vs scipy's FFT-based) — adequate for RMS-based bilateral symmetry analysis
- `filters.butter_bandpass` and `filters.notch` accept the old argument signatures but ignore them (uses config); callers do not need updating
- `features.py` warns at runtime if the detected sample rate differs >10% from `CFG.DEVICE_SAMPLE_RATE`

---

## Current Build State

Build was in progress when this context was written. The last attempted build step was the python-for-android compile phase. With scipy/matplotlib removed, the gfortran/NDK r21e issue no longer applies. Next build should only require:

```bash
cd ~/otb-mobile
VIRTUAL_ENV=1 buildozer android debug
```

If `.buildozer/` contains stale artifacts from previous scipy-inclusive builds, clean first:

```bash
VIRTUAL_ENV=1 buildozer android clean
VIRTUAL_ENV=1 buildozer android debug
```
