# Tab Interface Guide

## Overview
The `BaseTab` class provides a standardized interface for creating tabs in the application, ensuring consistent layout and behavior across all tabs. For windows with shared content areas (like the Data Analysis window), standalone panel classes provide a similar organizational pattern.

## Design Pattern
This follows an **Abstract Base Class (ABC)** pattern similar to C# interfaces, enforcing implementation of required methods while providing shared functionality.

## Standardized Layout Structure

Every tab following the `BaseTab` interface will have:

```
┌─────────────────────────────────────────────────────────────┐
│  Top Control Bar (inherited from parent window)             │
│  [Plot Time] [Calibrate] [Start Stream] [Start Recording]   │
├──────────────────────────────────────┬──────────────────────┤
│                                      │                      │
│  Content Area (stretch=3)            │  Control Panel       │
│  - Main visualizations               │  (stretch=0)         │
│  - Plots                             │  - Tab-specific      │
│  - Usually scrollable                │    buttons           │
│                                      │  - Max width: 200px  │
│                                      │                      │
└──────────────────────────────────────┴──────────────────────┘
```

## Current Implementations

### Live Streaming Window (SoundtrackWindow)
Uses `BaseTab` subclasses for all 4 tabs:

| Tab Class | File | Purpose |
|-----------|------|---------|
| `AllTracksTab` | `app/ui/tabs/tab_implementations.py` | All data tracks with channel/track selection |
| `HDsEMGTab` | `app/ui/tabs/tab_implementations.py` | HDsEMG plots with averaged channel controls |
| `FeaturesTab` | `app/ui/tabs/tab_implementations.py` | Feature extraction results |
| `HeatmapTab` | `app/ui/tabs/tab_implementations.py` | 8x8 HD-EMG heatmap normalized to MVC |

Usage in `main_window.py`:
```python
from app.ui.tabs.tab_implementations import AllTracksTab, HDsEMGTab, FeaturesTab, HeatmapTab

self.all_tracks_tab = AllTracksTab()
self.hdsemg_tab = HDsEMGTab()
self.features_tab = FeaturesTab()
self.heatmap_tab = HeatmapTab()

for tab in [self.all_tracks_tab, self.hdsemg_tab, self.features_tab, self.heatmap_tab]:
    self.tabs.addTab(tab, tab.get_tab_name())
```

Accessing tab internals (e.g., scroll layouts for TrackManager, buttons for signal wiring):
```python
# Scroll layouts
self.all_tracks_tab.scroll_layout
self.hdsemg_tab.hdsemg_scroll_layout
self.features_tab.feature_scroll_layout

# Buttons
self.all_tracks_tab.select_channels_button.clicked.connect(handler)
self.hdsemg_tab.hd_average_select_button.clicked.connect(handler)
```

### Data Analysis Window (DataAnalysisWindow)
Uses standalone panel classes (not BaseTab) because the window has a shared plot area visible across all tabs. Only the control panels switch when tabs change.

| Panel Class | File | Purpose |
|-------------|------|---------|
| `DataViewingPanel` | `app/ui/panels/data_viewing_panel.py` | Channel selection and signal processing controls |
| `FeaturesPanel` | `app/ui/panels/features_panel.py` | Feature analysis buttons |

Usage in `data_analysis_window.py`:
```python
from app.ui.panels.data_viewing_panel import DataViewingPanel
from app.ui.panels.features_panel import FeaturesPanel

self.data_viewing_panel = DataViewingPanel()
self.content_tabs.addTab(self.data_viewing_panel, "Data Viewing")

self.features_panel = FeaturesPanel()
self.content_tabs.addTab(self.features_panel, "Features")
```

Accessing panel widgets:
```python
self.data_viewing_panel.channel1_combo.currentIndexChanged.connect(handler)
self.features_panel.activation_timings_button.clicked.connect(handler)
```

## Creating a New Tab

### Step 1: Import the Base Class

```python
from PyQt5 import QtWidgets
from app.ui.tabs.base_tab import BaseTab
```

### Step 2: Create Your Tab Class

```python
class MyNewTab(BaseTab):
    """Description of what this tab does."""

    def __init__(self, parent=None):
        # Initialize any instance variables BEFORE calling super().__init__()
        self.my_data = []
        self.my_button = None
        super().__init__(parent)

    def create_content_area(self) -> QtWidgets.QWidget:
        """Create the main content area."""
        scroll_area, scroll_widget, self.scroll_layout = self.create_scroll_area()
        return scroll_area

    def create_control_panel(self) -> QtWidgets.QWidget:
        """Create the control panel with tab-specific buttons."""
        self.my_button = QtWidgets.QPushButton("My Control")
        return self.create_control_panel_base([self.my_button])

    def get_tab_name(self) -> str:
        """Return the tab display name."""
        return "My Tab Name"
```

### Step 3: Add Tab to the Window

```python
from app.ui.tabs.tab_implementations import MyNewTab

self.my_tab = MyNewTab()
self.tabs.addTab(self.my_tab, self.my_tab.get_tab_name())

# Wire signals in _connect_signals()
self.my_tab.my_button.clicked.connect(self.on_my_button_clicked)
```

**Important:** Store buttons as `self.` attributes on the tab class so the parent window can wire signals to them.

## Creating a New Panel (for shared-content windows)

For windows where multiple tabs share the same content area, create standalone panel classes:

```python
from PyQt5 import QtWidgets

class MyPanel(QtWidgets.QWidget):
    """Control panel for specific functionality."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.my_button = QtWidgets.QPushButton("Do Something")
        layout.addWidget(self.my_button)
        layout.addStretch()
```

## Required Methods (BaseTab)

All tabs **must** implement these three methods:

### 1. `create_content_area() -> QtWidgets.QWidget`
Returns the main content widget (left side, stretch=3).

**Common patterns:**
- Scrollable plot area: Use `self.create_scroll_area()`
- Single visualization: Return a plot widget directly
- Complex layout: Create and return a custom widget with its own layout

### 2. `create_control_panel() -> QtWidgets.QWidget`
Returns the control panel widget (right side, stretch=0).

**Best practice:**
- Store buttons as `self.` attributes for external signal wiring
- Use `self.create_control_panel_base([button1, button2, ...])` for standard panels
- Max width is automatically set to 200px

### 3. `get_tab_name() -> str`
Returns the display name for the tab.

## Utility Methods

### `create_scroll_area()`
Creates a standard scroll area setup.

```python
scroll_area, scroll_widget, scroll_layout = self.create_scroll_area()
scroll_layout.addWidget(my_widget)
return scroll_area
```

**Returns:** `(QScrollArea, QWidget, QVBoxLayout)`

### `create_control_panel_base(buttons=None)`
Creates a standard control panel.

```python
self.button1 = QtWidgets.QPushButton("Button 1")
self.button2 = QtWidgets.QPushButton("Button 2")
panel = self.create_control_panel_base([self.button1, self.button2])
return panel
```

**Parameters:**
- `buttons` (optional): List of QPushButton widgets to add

**Returns:** `QWidget` with vertical layout and stretch at bottom

## File Structure

```
app/ui/
├── tabs/
│   ├── __init__.py
│   ├── base_tab.py              # BaseTab abstract class
│   └── tab_implementations.py   # AllTracksTab, HDsEMGTab, FeaturesTab, HeatmapTab
├── panels/
│   ├── __init__.py
│   ├── data_viewing_panel.py    # DataViewingPanel
│   └── features_panel.py        # FeaturesPanel
└── windows/
    ├── main_window.py           # Uses BaseTab tabs
    └── data_analysis_window.py  # Uses panel classes
```

## Future Enhancements

The BaseTab interface can be extended with:
- Common update methods (e.g., `update_display()`)
- Data validation hooks
- Save/load functionality
- Export capabilities
- Theme support

Add these to `BaseTab` and all tabs inherit them automatically.
