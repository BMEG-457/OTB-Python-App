# Project Directory Restructuring

## New Directory Structure

The project has been reorganized into a clean, modular structure with logical grouping of related files:

```
BMEG 457 scripts/
├── main.py                      # Application entry point
├── app/
│   ├── __init__.py
│   │
│   ├── core/                    # Core application classes
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration constants
│   │   ├── device.py           # Device abstraction (SessantaquattroPlus)
│   │   └── track.py            # Track class for signal visualization
│   │
│   ├── data/                    # Data handling layer
│   │   ├── __init__.py
│   │   └── data_receiver.py    # Thread for receiving data from device
│   │
│   ├── managers/                # Business logic managers
│   │   ├── __init__.py
│   │   ├── recording_manager.py      # Recording & CSV export
│   │   ├── streaming_controller.py   # Live streaming control
│   │   └── track_manager.py          # Track initialization & management
│   │
│   ├── processing/              # Signal processing pipeline
│   │   ├── __init__.py
│   │   ├── features.py         # Feature extraction (RMS, etc.)
│   │   ├── filters.py          # Signal filters (bandpass, notch, rectify)
│   │   ├── pipeline.py         # Processing pipeline framework
│   │   └── transforms.py       # Transformations (FFT, etc.)
│   │
│   ├── ui/                      # User interface components
│   │   ├── __init__.py
│   │   │
│   │   ├── dialogs/            # Modal dialogs
│   │   │   ├── __init__.py
│   │   │   └── dialogs.py      # Calibration, channel selection, track visibility
│   │   │
│   │   ├── tabs/               # Tab implementations
│   │   │   ├── __init__.py
│   │   │   ├── base_tab.py     # Abstract base class for tabs
│   │   │   └── tab_implementations.py  # Concrete tab implementations
│   │   │
│   │   └── windows/            # Main windows
│   │       ├── __init__.py
│   │       ├── main_window.py  # Main application window (formerly window.py)
│   │       └── control_window.py  # Control window (legacy)
│   │
│   └── docs/                    # Documentation
│       ├── REFACTORING_SUMMARY.md     # Previous refactoring summary
│       └── TAB_INTERFACE_GUIDE.md     # Tab interface documentation
│
├── data/                        # Data storage (user data)
└── tests/                       # Test files
```

## Organization Principles

### 1. **Separation of Concerns**
Each directory has a single, clear responsibility:
- `core/` - Fundamental classes used throughout the app
- `data/` - Data acquisition and handling
- `managers/` - Business logic orchestration
- `processing/` - Signal processing algorithms
- `ui/` - User interface components

### 2. **Hierarchical Structure**
- Top-level directories represent major architectural layers
- Subdirectories provide fine-grained organization
- Clear parent-child relationships

### 3. **Discoverability**
- Related files are grouped together
- Directory names clearly indicate their contents
- Consistent naming conventions

## File Purpose by Directory

### `core/` - Application Foundation
| File | Purpose |
|------|---------|
| `config.py` | Application-wide configuration constants |
| `device.py` | Hardware device abstraction and communication |
| `track.py` | Signal track visualization with circular buffering |

### `data/` - Data Layer
| File | Purpose |
|------|---------|
| `data_receiver.py` | Background thread for receiving & processing device data |

### `managers/` - Business Logic
| File | Purpose |
|------|---------|
| `recording_manager.py` | Manages recording state, CSV export, overflow protection |
| `streaming_controller.py` | Controls live data streaming (start/stop/pause) |
| `track_manager.py` | Initializes and manages all visualization tracks |

### `processing/` - Signal Processing
| File | Purpose |
|------|---------|
| `features.py` | Feature extraction algorithms (RMS, etc.) |
| `filters.py` | Signal filtering (bandpass, notch, rectify) |
| `pipeline.py` | Configurable processing pipeline framework |
| `transforms.py` | Signal transformations (FFT, etc.) |

### `ui/dialogs/` - User Dialogs
| File | Purpose |
|------|---------|
| `dialogs.py` | CalibrationDialog, ChannelSelectorDialog, TrackVisibilityDialog |

### `ui/tabs/` - Tab System
| File | Purpose |
|------|---------|
| `base_tab.py` | Abstract base class enforcing tab interface |
| `tab_implementations.py` | Concrete tab classes (Heatmap, AllTracks, etc.) |

### `ui/windows/` - Application Windows
| File | Purpose |
|------|---------|
| `main_window.py` | Main application window (SoundtrackWindow) - formerly `window.py` |
| `control_window.py` | Legacy control window (not currently used) |

### `docs/` - Documentation
| File | Purpose |
|------|---------|
| `REFACTORING_SUMMARY.md` | Summary of the code refactoring |
| `TAB_INTERFACE_GUIDE.md` | Guide for implementing new tabs |

## Import Statement Updates

All import statements have been updated to reflect the new structure:

### Before:
```python
from app.config import Config
from app.device import SessantaquattroPlus
from app.window import SoundtrackWindow
from app.dialogs import CalibrationDialog
from app.track_manager import TrackManager
```

### After:
```python
from app.core.config import Config
from app.core.device import SessantaquattroPlus
from app.ui.windows.main_window import SoundtrackWindow
from app.ui.dialogs.dialogs import CalibrationDialog
from app.managers.track_manager import TrackManager
```

## Benefits

### 1. **Improved Navigation**
- Developers can quickly locate related files
- Clear directory structure reduces cognitive load
- Logical grouping aids understanding

### 2. **Scalability**
- Easy to add new files to appropriate directories
- Clear where new functionality should go
- Room for growth without clutter

### 3. **Maintainability**
- Changes are localized to specific directories
- Dependencies are clearer
- Easier to refactor individual components

### 4. **Testing**
- Test files can mirror the app structure
- Unit tests organized by component
- Integration tests clearly separated

### 5. **Documentation**
- Dedicated docs directory
- Easy to find all documentation
- Can add more docs without cluttering code

## Migration Notes

### Files Renamed:
- `window.py` → `ui/windows/main_window.py`

### Files Moved:
- Core classes → `core/`
- Managers → `managers/`
- Data handling → `data/`
- UI components → `ui/` with subdirectories
- Documentation → `docs/`

### All Imports Updated:
- ✅ `main.py`
- ✅ `main_window.py`
- ✅ `track_manager.py`
- ✅ `tab_implementations.py`

### Verification:
- ✅ No syntax errors
- ✅ All imports resolve correctly
- ✅ Directory structure is clean and logical
- ✅ `__init__.py` files in all packages

## Next Steps

1. **Clean up `__pycache__`**: Old .pyc files reference old structure
   ```powershell
   Get-ChildItem -Path app -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force
   ```

2. **Test the application**: Verify all functionality works with new structure

3. **Update tests**: If tests exist, update their imports

4. **Consider adding**:
   - `README.md` in each major directory explaining its purpose
   - Module-level docstrings documenting public APIs
   - Additional documentation in `docs/` directory

## Conclusion

The project is now organized following industry best practices with:
- Clear separation of concerns
- Logical directory hierarchy
- Improved discoverability
- Better scalability
- Enhanced maintainability

The structure supports future growth while keeping the codebase clean and organized.
