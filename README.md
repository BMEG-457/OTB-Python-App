# OTB-Python-App

A PyQt5-based desktop application for real-time High-Density Surface Electromyography (HDsEMG) signal acquisition, visualization, and analysis. Designed for the OTBioelettronica Sessantaquattro+ device (64-channel EMG system).

## Features

### Real-Time Signal Visualization
- **Multi-channel EMG display** with configurable time windows
- **HD-EMG visualization** with per-channel plots and averaged signals
- **Feature extraction displays** (RMS, MAV, FFT, etc.)
- **8×8 heatmap** showing muscle activity normalized to MVC (Maximum Voluntary Contraction)
- Interactive plot controls (pause, time scale adjustment)

### Signal Processing Pipeline
- **Bandpass filtering** (20-450 Hz, configurable)
- **Notch filtering** (60 Hz powerline interference removal)
- **Full-wave rectification**
- **Envelope detection** (5 Hz low-pass)
- **FFT analysis** for frequency domain visualization
- **RMS calculation** with configurable window sizes

### Calibration System
- Two-phase calibration protocol:
  1. **Rest phase**: Establishes baseline RMS values
  2. **MVC phase**: Records maximum voluntary contraction
- Automatic threshold calculation (baseline + 3×std)
- Per-channel calibration values

### Advanced EMG Analysis
- **Contraction detection** with spike-robust algorithm:
  - Rate-of-change detection with smoothing
  - Hysteresis-based onset/offset detection
  - Automatic contraction merging
  - Refractory period to prevent false triggers
- **Activation timing** analysis
- **Time-to-fatigue** detection (RMS and median frequency methods)
- **Muscle strength metrics** relative to MVC

### Data Recording & Export
- Stream data to CSV format with timestamps
- Automatic overflow protection (1M sample limit)
- Channel-wise data organization
- Recording state persistence

## Installation

### Prerequisites
- Python 3.8 or higher
- OTBioelettronica Sessantaquattro+ device

### Setup

1. Clone the repository:
```bash
git clone https://github.com/BMEG-457/OTB-Python-App.git
cd OTB-Python-App
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Application

```bash
cd "BMEG 457 scripts"
python main.py
```

### Workflow

1. **Mode Selection**
   - Choose "Live Data Viewing" for real-time EMG acquisition
   - (Data Analysis mode in development)

2. **Initialize Connection**
   - Application connects to Sessantaquattro+ device
   - Wait for "Connected" status

3. **Calibration** (Required before recording)
   - Click "Calibrate" button
   - Follow on-screen instructions:
     - **Rest phase**: Relax muscles (3 seconds)
     - **Contraction phase**: Perform maximum voluntary contraction (3 seconds)
   - Review calibration summary (baseline, threshold, MVC)

4. **Live Streaming**
   - Click "Start Live Stream" to begin visualization
   - Use plot time dropdown to adjust time window (100ms - 10s)
   - Pause/resume streaming as needed

5. **Recording**
   - Click "Start Recording" after calibration
   - Data is automatically saved to CSV on stop
   - Files saved with timestamp: `emg_recording_YYYYMMDD_HHMMSS.csv`

### Interface Tabs

#### 1. Main Tab
- Overview of all signal tracks
- Quick access to all channels

#### 2. HDsEMG Tab
- Focused high-density EMG visualization
- Averaged channel display
- Select specific channels for averaging
- Individual channel inspection

#### 3. Features Tab
- Real-time feature extraction displays
- RMS, MAV, and other time-domain features
- FFT frequency analysis

#### 4. Heatmap Tab
- 8×8 spatial representation of muscle activity
- Normalized to MVC for relative strength
- Color-coded intensity map
- Real-time updates during streaming

## Configuration

### Signal Processing Parameters

Edit `BMEG 457 scripts/app/core/config.py`:

```python
# Filter parameters
BANDPASS_LOW = 20      # Hz
BANDPASS_HIGH = 450    # Hz
NOTCH_FREQ = 60        # Hz (powerline interference)

# Feature extraction
WINDOW_SIZE_MS = 200   # RMS/MAV window size in milliseconds

# Contraction detection
RATE_THRESHOLD = 0.005      # V/s for onset detection
SMOOTHING_WINDOW = 5        # Spike smoothing window
HYSTERESIS_FACTOR = 0.5     # Offset sensitivity (0.3-0.7)
MIN_CONTRACTION_DURATION = 0.3  # seconds
```

### Device Configuration

Device settings in `BMEG 457 scripts/app/core/device.py`:
- Sampling frequency
- Channel count and layout
- Track definitions and conversions

## Architecture

### Project Structure

```
BMEG 457 scripts/
├── main.py                 # Application entry point
├── app/
│   ├── core/              # Core classes
│   │   ├── config.py      # Configuration constants
│   │   ├── device.py      # Device abstraction
│   │   └── track.py       # Signal track visualization
│   │
│   ├── data/              # Data handling
│   │   └── data_receiver.py  # Thread for device communication
│   │
│   ├── managers/          # Business logic
│   │   ├── recording_manager.py    # Recording & CSV export
│   │   ├── streaming_controller.py # Live streaming control
│   │   └── track_manager.py        # Track management
│   │
│   ├── processing/        # Signal processing
│   │   ├── features.py    # EMG feature extraction
│   │   ├── filters.py     # Signal filters
│   │   ├── pipeline.py    # Processing pipeline framework
│   │   └── transforms.py  # FFT and other transforms
│   │
│   └── ui/                # User interface
│       ├── dialogs/       # Calibration, channel selection
│       ├── tabs/          # Tab implementations
│       └── windows/       # Main application window
│
└── data/                  # Recorded data and test files
```

### Key Design Patterns

- **Manager Pattern**: Separate managers for recording, streaming, and track management
- **Pipeline Pattern**: Modular signal processing pipeline
- **Observer Pattern**: PyQt signals for event handling
- **Abstract Base Class**: Standardized tab interface

## Development

### Adding New Features

1. **New Signal Processing Stage**:
   - Add function to `app/processing/filters.py` or `transforms.py`
   - Register in pipeline: `get_pipeline('name').add_stage(function)`

2. **New EMG Analysis Function**:
   - Add to `app/processing/features.py`
   - Functions receive calibrated baseline/threshold values
   - Follow existing function signatures

3. **New Visualization Tab**:
   - Create class inheriting from `BaseTab`
   - Implement `create_content_area()` and `create_control_panel()`
   - Add to tab widget in `main_window.py`

### Testing

Run the test notebook for signal processing validation:
```bash
jupyter notebook "data/test copy copy.ipynb"
```

## Dependencies

- **PyQt5** (5.15.11): GUI framework
- **pyqtgraph** (0.13.7): Real-time plotting
- **NumPy** (2.3.5): Numerical computations
- **SciPy** (1.16.3): Signal processing (filters, FFT, spectrogram)
- **xmltodict** (1.0.2): Device configuration parsing

See `requirements.txt` for complete list with versions.

## Hardware Requirements

- **OTBioelettronica Sessantaquattro+ device**
  - 64-channel EMG acquisition
  - Typical sampling rate: ~2 kHz
  - Network connection (Ethernet/WiFi)

## Known Limitations

- Maximum recording duration: ~8 minutes at 2 kHz (1M sample limit)
- Network latency affects real-time visualization
- Heatmap assumes 8×8 electrode grid layout

## Contributing

This project is part of BMEG 457 coursework. For contributions or issues:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request with detailed description

## License

Educational use for BMEG 457 course.

## Acknowledgments

- OTBioelettronica for Sessantaquattro+ device specifications
- BMEG 457 course staff and students

## Contact

For questions or support, contact the BMEG 457 development team.
