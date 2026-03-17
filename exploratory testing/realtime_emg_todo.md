# Real-Time EMG Contraction Detection - Implementation Plan

## Overview
Implement a real-time EMG contraction detection system that provides visual feedback (icon/indicator) when a muscle contraction is detected.

---

## Phase 1: Core Real-Time Processing

### 1.1 Causal Filter Implementation
- [ ] Replace `filtfilt` with `lfilter` for real-time compatibility
- [ ] Implement filter state management (maintain `zi` between chunks)
- [ ] Create `RealtimeFilter` class to handle streaming data
- [ ] Test filter settling time and phase delay

### 1.2 Streaming TKEO Implementation
- [ ] Adapt TKEO to work on streaming chunks
- [ ] Handle chunk boundaries (need overlap of 1 sample)
- [ ] Create `RealtimeTKEO` class

### 1.3 Threshold-Crossing Detection
- [ ] Replace peak-finding with rising-edge threshold crossing
- [ ] Implement refractory period (prevent re-trigger for ~300ms)
- [ ] Add hysteresis (separate on/off thresholds) to prevent chatter
- [ ] Create `ContractionDetector` class

---

## Phase 2: Data Acquisition

### 2.1 EMG Hardware Interface
- [ ] Identify data source (serial port, Bluetooth, USB, etc.)
- [ ] Implement data reader with appropriate protocol
- [ ] Handle connection/disconnection gracefully
- [ ] Buffer incoming samples

### 2.2 Timing and Synchronization
- [ ] Determine/configure sampling rate from hardware
- [ ] Handle timestamp generation if not provided by hardware
- [ ] Implement circular buffer for efficient memory use

---

## Phase 3: User Interface

### 3.1 Visual Indicator
- [ ] Choose GUI framework (tkinter recommended for simplicity)
- [ ] Create main window with contraction indicator
- [ ] Implement indicator states (idle, active, cooldown)
- [ ] Add color coding (e.g., gray → green on contraction)

### 3.2 Real-Time Plot (Optional)
- [ ] Add live scrolling EMG trace using matplotlib animation or pyqtgraph
- [ ] Show threshold line on plot
- [ ] Mark detected contractions on trace

### 3.3 Configuration Panel (Optional)
- [ ] Threshold adjustment slider
- [ ] Refractory period control
- [ ] Baseline calibration button

---

## Phase 4: Calibration

### 4.1 Baseline Calibration
- [ ] Implement "rest period" calibration (collect 1-2 seconds at startup)
- [ ] Calculate baseline mean and std from rest period
- [ ] Set initial threshold based on calibration

### 4.2 Adaptive Thresholding (Optional)
- [ ] Implement running baseline estimation
- [ ] Auto-adjust threshold based on signal statistics
- [ ] Add manual override option

---

## Phase 5: Integration and Testing

### 5.1 Main Loop Architecture
- [ ] Design event-driven or polling-based main loop
- [ ] Ensure UI remains responsive during processing
- [ ] Use threading or asyncio if needed

### 5.2 Performance Testing
- [ ] Measure end-to-end latency (target: <100ms)
- [ ] Test with various contraction speeds
- [ ] Verify no missed detections or false positives

### 5.3 Edge Cases
- [ ] Handle signal dropout
- [ ] Handle noise spikes
- [ ] Test with sustained contractions
- [ ] Test with rapid repeated contractions

---

## Technical Specifications

| Parameter | Target Value |
|-----------|--------------|
| Sampling rate | 1000+ Hz (match hardware) |
| Processing chunk size | 10-50 samples (~10-50ms) |
| Filter delay | ~20-50ms |
| Detection latency | <100ms total |
| Refractory period | 300ms (configurable) |
| Threshold | Baseline mean + 8*std (TKEO) |

---

## File Structure (Proposed)

```
realtime_emg/
├── __init__.py
├── filters.py          # RealtimeFilter, RealtimeTKEO
├── detector.py         # ContractionDetector
├── acquisition.py      # EMG hardware interface
├── ui.py               # GUI components
├── calibration.py      # Baseline calibration
└── main.py             # Main application entry point
```

---

## Dependencies

- numpy
- scipy (for filter design)
- pyserial (if using serial port)
- tkinter (built-in) or PyQt5
- matplotlib or pyqtgraph (for live plotting)

---

## References

- Teager-Kaiser Energy Operator for EMG onset detection
- Li, X., Zhou, P., & Aruin, A. S. (2007). Teager-Kaiser energy operation of surface EMG improves muscle activity onset detection.
- Hodges, P. W., & Bui, B. H. (1996). A comparison of computer-based methods for the determination of onset of muscle contraction using electromyography.
