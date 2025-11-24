# Tab Interface Guide

## Overview
The `BaseTab` class provides a standardized interface for creating tabs in the application, ensuring consistent layout and behavior across all tabs.

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

## Creating a New Tab

### Step 1: Import the Base Class

```python
from PyQt5 import QtWidgets
from app.base_tab import BaseTab
```

### Step 2: Create Your Tab Class

```python
class MyNewTab(BaseTab):
    """
    Description of what this tab does.
    """
    
    def __init__(self, parent=None):
        # Initialize any instance variables BEFORE calling super().__init__()
        self.my_data = []
        super().__init__(parent)
    
    def create_content_area(self) -> QtWidgets.QWidget:
        """Create the main content area."""
        # Option 1: Use the utility method for scrollable content
        scroll_area, scroll_widget, scroll_layout = self.create_scroll_area()
        
        # Add your widgets to scroll_layout
        my_plot = QtWidgets.QLabel("My Plot Here")
        scroll_layout.addWidget(my_plot)
        scroll_layout.addStretch()
        
        return scroll_area
        
        # Option 2: Return any QWidget for custom layouts
        # my_custom_widget = QtWidgets.QWidget()
        # return my_custom_widget
    
    def create_control_panel(self) -> QtWidgets.QWidget:
        """Create the control panel with tab-specific buttons."""
        # Create your buttons
        my_button1 = QtWidgets.QPushButton("My Control 1")
        my_button2 = QtWidgets.QPushButton("My Control 2")
        
        # Connect signals
        my_button1.clicked.connect(self.on_my_button1_clicked)
        
        # Use utility method to create panel
        return self.create_control_panel_base([my_button1, my_button2])
    
    def get_tab_name(self) -> str:
        """Return the tab display name."""
        return "My Tab Name"
    
    # Add your custom methods
    def on_my_button1_clicked(self):
        """Handle button click."""
        print("Button clicked!")
```

### Step 3: Add Tab to Main Window

In `window.py`:

```python
from app.tab_implementations import MyNewTab

# In the __init__ method where tabs are created:
my_tab = MyNewTab(self)
self.tabs.addTab(my_tab, my_tab.get_tab_name())

# Store reference if you need to access it later
self.my_tab = my_tab
```

## Required Methods

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
- Use `self.create_control_panel_base([button1, button2, ...])` for standard panels
- Max width is automatically set to 200px
- Buttons are added vertically with stretch at the bottom

### 3. `get_tab_name() -> str`
Returns the display name for the tab.

## Utility Methods

### `create_scroll_area()`
Creates a standard scroll area setup.

```python
scroll_area, scroll_widget, scroll_layout = self.create_scroll_area()
# Add widgets to scroll_layout
scroll_layout.addWidget(my_widget)
return scroll_area
```

**Returns:** `(QScrollArea, QWidget, QVBoxLayout)`

### `create_control_panel_base(buttons=None)`
Creates a standard control panel.

```python
button1 = QtWidgets.QPushButton("Button 1")
button2 = QtWidgets.QPushButton("Button 2")
panel = self.create_control_panel_base([button1, button2])
return panel
```

**Parameters:**
- `buttons` (optional): List of QPushButton widgets to add

**Returns:** `QWidget` with vertical layout and stretch at bottom

## Benefits of Using BaseTab

1. **Consistency**: All tabs follow the same layout pattern
2. **Maintainability**: Changes to the base layout affect all tabs automatically
3. **Reduced Boilerplate**: Utility methods handle common setup
4. **Type Safety**: Abstract methods must be implemented
5. **Extensibility**: Easy to add new shared functionality
6. **Documentation**: Clear contract for what each tab must provide

## Migration Guide

### Before (Manual Layout)
```python
# Old approach - lots of boilerplate
heatmap_content = QtWidgets.QWidget()
heatmap_layout = QtWidgets.QHBoxLayout(heatmap_content)

# Create content
heatmap_view = pg.GraphicsLayoutWidget()
heatmap_layout.addWidget(heatmap_view, stretch=3)

# Create panel
panel = QtWidgets.QWidget()
panel_layout = QtWidgets.QVBoxLayout(panel)
panel_layout.addStretch()
heatmap_layout.addWidget(panel, stretch=0)

self.tabs.addTab(heatmap_content, "Heatmap")
```

### After (BaseTab Interface)
```python
# New approach - clean and standardized
class HeatmapTab(BaseTab):
    def create_content_area(self):
        return pg.GraphicsLayoutWidget()
    
    def create_control_panel(self):
        return self.create_control_panel_base()
    
    def get_tab_name(self):
        return "Heatmap"

# Usage
heatmap_tab = HeatmapTab(self)
self.tabs.addTab(heatmap_tab, heatmap_tab.get_tab_name())
```

## Examples

See `app/tab_implementations.py` for complete implementations of:
- `HeatmapTab` - Visualization-heavy tab
- `AllTracksTab` - Scrollable content with multiple controls
- `HDsEMGTab` - Specialized data display
- `FeaturesTab` - Feature extraction display

## Future Enhancements

The BaseTab interface can be extended with:
- Common update methods (e.g., `update_display()`)
- Data validation hooks
- Save/load functionality
- Export capabilities
- Theme support

Add these to `BaseTab` and all tabs inherit them automatically.
