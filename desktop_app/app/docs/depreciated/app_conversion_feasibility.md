# Feasibility Analysis: Converting Python EMG App to Mobile/Web

## Current Application Overview

The app is a **PyQt5 desktop application** for EMG signal acquisition and analysis with:
- **Hardware dependency**: OTBioelettronica Sessantaquattro+ 64-channel EMG device (TCP socket on 192.168.1.x)
- **Real-time visualization**: pyqtgraph with GPU acceleration
- **Signal processing**: Bandpass, notch, envelope, FFT, contraction detection, fatigue analysis
- **Two modes**: Live streaming and post-session CSV analysis

### Application Architecture

```
app/
├── core/                        # Device & visualization
│   ├── device.py               # TCP/socket communication
│   ├── config.py               # Global constants
│   ├── track.py                # Real-time plot buffers (live mode)
│   └── analysis_track.py       # Static data visualization (post-session)
├── data/                        # Data I/O
│   ├── data_receiver.py        # QThread for socket data receipt
│   └── csv_loader.py           # CSV parsing with multi-resolution support
├── managers/                    # Business logic coordination
│   ├── recording_manager.py    # Data collection & CSV export
│   ├── streaming_controller.py # Live streaming state
│   ├── track_manager.py        # Track lifecycle (live)
│   ├── analysis_track_manager.py # Track lifecycle (post-session)
│   └── time_navigation_controller.py # Time slider/scrubbing
├── processing/                  # Signal processing (PORTABLE)
│   ├── pipeline.py             # Modular pipeline framework
│   ├── filters.py              # Bandpass, notch, envelope, rectification
│   ├── features.py             # RMS, MAV, fatigue, contraction detection
│   └── transforms.py           # FFT (future: STFT, wavelets)
└── ui/                          # User interface (REQUIRES REWRITE)
    ├── windows/
    │   ├── main_window.py      # Live streaming window
    │   └── data_analysis_window.py # Post-session analysis
    ├── dialogs/                # Calibration, channel selection
    └── tabs/                   # BaseTab interface & implementations
```

---

## Critical Blocker (Both Options)

**Hardware connectivity**: The EMG device requires direct network access on a local subnet (192.168.1.x). Both mobile and web would need either:
1. A **gateway server** running on the same network as the device, or
2. Running in a **local network environment** where the device is accessible

---

## Comparison: Android App vs Web Application

| Factor | Android App | Web Application |
|--------|-------------|-----------------|
| **UI Rewrite Effort** | ~80% (Kotlin/Jetpack Compose) | ~70% (React/Vue + charting library) |
| **Backend Effort** | Same as web (shared Python API) | Python FastAPI/Flask backend |
| **Real-time Visualization** | Native charts (MPAndroidChart) | Plotly.js, ECharts, or Chart.js |
| **Device Connectivity** | Requires gateway server | Can run gateway on same machine |
| **Offline Capability** | Excellent (SQLite, local storage) | Limited (requires connectivity) |
| **Distribution** | Play Store, APK sideload | URL access, no install needed |
| **Development Stack** | Kotlin + Python backend | JavaScript/TypeScript + Python |
| **Cross-platform** | Android only | Any browser (desktop, mobile, tablet) |
| **Real-time Performance** | Better (native threading) | Good (WebSockets, Web Workers) |
| **File Access** | Requires permissions | Browser sandbox limitations |

---

## Work Required: Web Application

### Backend (Python - Moderate effort)

| Task | Complexity | Notes |
|------|------------|-------|
| Extract processing pipeline to library | Low | `pipeline.py`, `filters.py`, `features.py` are already modular |
| Create REST API (FastAPI/Flask) | Medium | Endpoints: `/upload`, `/process`, `/calibrate`, `/stream` |
| WebSocket for real-time streaming | Medium | Replace QThread with asyncio |
| Device gateway service | Medium | Wrap `device.py` as network proxy |
| Database for sessions/recordings | Low | PostgreSQL or SQLite |

### Frontend (JavaScript - High effort)

| Task | Complexity | Notes |
|------|------------|-------|
| Live streaming view | High | Replace pyqtgraph with Plotly/ECharts |
| Post-session analysis view | Medium | Time navigation, channel selection |
| Heatmap visualization | Medium | 8×8 grid with color mapping |
| Calibration workflow | Low | Form-based UI |
| File upload/download | Low | Standard browser APIs |

**Total Estimated Effort**: 60-70% rewrite

---

## Work Required: Android App

### Backend (Same as Web)
- Shared Python API server
- WebSocket streaming endpoint
- Device gateway service

### Native Android (Kotlin - High effort)

| Task | Complexity | Notes |
|------|------------|-------|
| Real-time chart rendering | High | MPAndroidChart or custom Canvas |
| WebSocket client for streaming | Medium | OkHttp or Ktor |
| Post-session analysis UI | High | RecyclerView, custom views |
| Heatmap visualization | Medium | Custom View with Canvas drawing |
| Local database (Room) | Low | Session caching, offline support |
| File picker integration | Low | Storage Access Framework |
| Background service for recording | Medium | Foreground service with notification |

**Total Estimated Effort**: 70-80% rewrite (plus learning curve if not familiar with Android)

---

## Recommendation

| Scenario | Best Choice | Rationale |
|----------|-------------|-----------|
| **Research/lab use (fixed location)** | **Web App** | Easier deployment, no install needed, runs on any device with browser |
| **Field use / portable** | **Android App** | Better offline support, native performance for real-time display |
| **Quick MVP / prototyping** | **Web App** | Faster development cycle, easier to iterate |
| **Long-term product** | **Both** | Shared backend, native mobile + web dashboard |

---

## Reusable Components (Zero Migration)

These files can be extracted directly into a shared Python backend with no modification:

| File | Purpose |
|------|---------|
| `processing/pipeline.py` | Modular processing framework |
| `processing/filters.py` | Bandpass, notch, rectification, envelope |
| `processing/features.py` | RMS, MAV, contraction detection, fatigue analysis |
| `processing/transforms.py` | FFT transforms |
| `data/csv_loader.py` | CSV parsing (minor refactor needed) |

**~30% of the codebase is directly portable** to either option.

---

## Proposed Architecture (Either Option)

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend                             │
│         (Web: React/Vue  OR  Android: Kotlin)           │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP/WebSocket
┌─────────────────────▼───────────────────────────────────┐
│                 Python Backend                          │
│    FastAPI + WebSocket + Extracted Processing Libs      │
└─────────────────────┬───────────────────────────────────┘
                      │ TCP Socket
┌─────────────────────▼───────────────────────────────────┐
│           EMG Device Gateway (Local Network)            │
│              192.168.1.x subnet                         │
└─────────────────────────────────────────────────────────┘
```

---

## Summary

| Aspect | Web Application | Android App |
|--------|-----------------|-------------|
| **Development Time** | Faster | Slower |
| **Accessibility** | Any device with browser | Android devices only |
| **Performance** | Good (WebSocket + modern JS) | Better (native) |
| **Offline Support** | Limited | Excellent |
| **Maintenance** | Single codebase | Separate native codebase |
| **Total Effort** | 60-70% rewrite | 70-80% rewrite |

**Bottom line**: Both are feasible. **Web is recommended** for faster development and broader accessibility unless offline/field use is critical. The signal processing code (~30% of the app) transfers directly to either option.
