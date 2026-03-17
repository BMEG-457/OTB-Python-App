# OTB-EMG Desktop App — Documentation Index

This document is an index. The full documentation has been split into focused files below.

---

## Documents

| Document | Audience | Contents |
|---|---|---|
| [USER_GUIDE.md](USER_GUIDE.md) | App users | Hardware setup, connecting, streaming, calibration, recording, tabs, data analysis, troubleshooting |
| [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | Developers | Project structure, entry point wiring, configuration system, TCP protocol, live data pipeline, signal processing, UI/tab architecture, build system |
| [DESIGN_RATIONALE.md](DESIGN_RATIONALE.md) | Developers / researchers | Justification and literature sources for every filter parameter, threshold, algorithm choice, and constant |

---

## Quick Architecture Summary

```
desktop_app/
├── main.py           Entry point. Creates all windows, wires buttons, owns device lifecycle.
├── config.json       All tunable parameters. Edit here, not in source files.
├── build.py          Runs PyInstaller to produce dist/OTB-EMG/
├── OTB-EMG.spec      PyInstaller build configuration
└── app/
    ├── core/         Device, config, path resolution, track buffer
    ├── data/         TCP receiver thread, CSV loader
    ├── managers/     Track, recording, streaming, time navigation
    ├── processing/   Filters, features, pipeline registry, realtime detector
    └── ui/           Windows, tabs (BaseTab pattern), panels, dialogs
```

For the full structure and explanation of each module, see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).

---

## Key Concepts at a Glance

- **Lazy connection**: the TCP socket is opened only when the user clicks Connect, not at startup.
- **Thread architecture**: `DataReceiverThread` (QThread) runs for the entire session; `StreamingController` only toggles a `running` flag.
- **Pipeline registry**: named lists of processing stages applied per incoming packet (`filtered`, `rectified`, `final`).
- **BaseTab**: abstract base class enforcing a two-panel layout (content left, controls right) for all live-mode tabs: `AllTracksTab`, `AccessoryTab`, `HDsEMGTab`, `HeatmapTab`, `IndividualChannelsTab`, `FeaturesTab`.
- **config.json**: single source of truth for all parameters; loaded once at startup by `Config`.
- **Path resolution**: `app/core/paths.py` handles source vs. frozen (PyInstaller) path differences.
