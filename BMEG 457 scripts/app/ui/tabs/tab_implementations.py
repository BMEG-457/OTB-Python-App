"""
Tab implementations using the BaseTab interface.
Each class provides a standardized tab with content area and control panel.
"""
from PyQt5 import QtWidgets
import pyqtgraph as pg
import numpy as np
from app.ui.tabs.base_tab import BaseTab


class AccessoryTab(BaseTab):
    """Accessory tab for non-EMG tracks (AUX, Quaternions, Buffer, Ramp)."""

    def __init__(self, parent=None):
        self.accessory_scroll_layout = None
        super().__init__(parent)

    def create_content_area(self) -> QtWidgets.QWidget:
        scroll_area, scroll_widget, self.accessory_scroll_layout = self.create_scroll_area()
        return scroll_area

    def create_control_panel(self) -> QtWidgets.QWidget:
        return self.create_control_panel_base()

    def get_tab_name(self) -> str:
        return "Accessory"


class HeatmapTab(BaseTab):
    """
    Heatmap tab implementation following the BaseTab interface.
    Displays an 8x8 HD-EMG array heatmap normalized to MVC.
    """
    
    def __init__(self, parent=None):
        # Initialize any state variables before calling super().__init__()
        self.heatmap_data = np.zeros((8, 8))
        self.heatmap_labels = []
        super().__init__(parent)
    
    def create_content_area(self) -> QtWidgets.QWidget:
        """Create the heatmap visualization."""
        # Create heatmap view
        heatmap_view = pg.GraphicsLayoutWidget()
        self.heatmap_plot = heatmap_view.addPlot()
        self.heatmap_plot.setAspectLocked(True)
        self.heatmap_plot.hideAxis('bottom')
        self.heatmap_plot.hideAxis('left')
        self.heatmap_plot.setTitle("HD-EMG Array Heatmap (Normalized to MVC)")
        
        # Create 8x8 ImageItem for heatmap
        self.heatmap_img = pg.ImageItem()
        self.heatmap_plot.addItem(self.heatmap_img)
        
        # Initialize with zeros
        self.heatmap_img.setImage(self.heatmap_data.T, levels=(0, 1))
        
        # Set colormap
        colormap = pg.colormap.get('viridis')
        self.heatmap_img.setColorMap(colormap)
        
        # Add colorbar
        colorbar = pg.ColorBarItem(values=(0, 1), colorMap=colormap)
        colorbar.setImageItem(self.heatmap_img)
        
        # Add text labels for channel numbers
        for row in range(8):
            for col in range(8):
                # Channel number: bottom-left is 1, going up by column
                channel_num = col * 8 + (7 - row) + 1
                text = pg.TextItem(str(channel_num), color='w', anchor=(0.5, 0.5))
                text.setPos(col + 0.5, row + 0.5)
                self.heatmap_plot.addItem(text)
                self.heatmap_labels.append(text)
        
        return heatmap_view
    
    def create_control_panel(self) -> QtWidgets.QWidget:
        """Create control panel (empty for now, ready for future controls)."""
        # No buttons needed yet, but could add:
        # - Colormap selector
        # - Scale adjustment
        # - Export options
        return self.create_control_panel_base()
    
    def get_tab_name(self) -> str:
        """Return the tab display name."""
        return "Heatmap"
    
    def update_heatmap(self, normalized_rms: np.ndarray):
        """
        Update the heatmap with new data.
        
        Args:
            normalized_rms: Array of 64 values normalized to [0, 1]
        """
        if len(normalized_rms) >= 64:
            # Reshape to 8x8 grid
            for col in range(8):
                for row in range(8):
                    channel_idx = col * 8 + (7 - row)
                    if channel_idx < len(normalized_rms):
                        self.heatmap_data[row, col] = normalized_rms[channel_idx]
            
            # Update the image
            self.heatmap_img.setImage(self.heatmap_data.T, levels=(0, 1))


_PRESET_MAP = {
    "2x2 Blocks (16)": "2x2_blocks",
    "Row Averages (8)": "rows",
    "Column Averages (8)": "columns",
}


class AllTracksTab(BaseTab):
    """
    All Tracks tab implementation following the BaseTab interface.
    Displays HDsEMG group average presets with a selector for switching views.
    """

    def __init__(self, parent=None):
        self.scroll_layout = None
        self.preset_selector = None
        super().__init__(parent)

    def create_content_area(self) -> QtWidgets.QWidget:
        """Create the scrollable area for all tracks."""
        scroll_area, scroll_widget, self.scroll_layout = self.create_scroll_area()
        return scroll_area

    def create_control_panel(self) -> QtWidgets.QWidget:
        """Create control panel with preset selector."""
        self.preset_selector = QtWidgets.QComboBox()
        self.preset_selector.addItems(list(_PRESET_MAP.keys()))
        return self.create_control_panel_base([self.preset_selector])

    def connect_signals(self, window):
        """Connect preset selector signal."""
        self.preset_selector.currentTextChanged.connect(
            lambda text: window.change_group_preset(_PRESET_MAP[text])
        )

    def get_tab_name(self) -> str:
        """Return the tab display name."""
        return "All Tracks"


class IndividualChannelsTab(BaseTab):
    """Dedicated tab for viewing and selecting individual HDsEMG channels."""

    def __init__(self, parent=None):
        self.individual_scroll_layout = None
        self.select_channels_button = None
        super().__init__(parent)

    def create_content_area(self) -> QtWidgets.QWidget:
        scroll_area, scroll_widget, self.individual_scroll_layout = self.create_scroll_area()
        return scroll_area

    def create_control_panel(self) -> QtWidgets.QWidget:
        self.select_channels_button = QtWidgets.QPushButton("Select Channels")
        return self.create_control_panel_base([self.select_channels_button])

    def connect_signals(self, window):
        self.select_channels_button.clicked.connect(window.open_channel_selector)

    def get_tab_name(self) -> str:
        return "Channels"


class HDsEMGTab(BaseTab):
    """
    HDsEMG tab implementation following the BaseTab interface.
    Displays HDsEMG-specific plots with averaged channel controls.
    """

    def __init__(self, parent=None):
        self.hdsemg_scroll_layout = None
        self.hd_average_select_button = None
        super().__init__(parent)
    
    def create_content_area(self) -> QtWidgets.QWidget:
        """Create the scrollable area for HDsEMG plots."""
        scroll_area, scroll_widget, self.hdsemg_scroll_layout = self.create_scroll_area()
        return scroll_area
    
    def create_control_panel(self) -> QtWidgets.QWidget:
        """Create control panel with average channel selector."""
        self.hd_average_select_button = QtWidgets.QPushButton("Select Avg Channels")

        return self.create_control_panel_base([self.hd_average_select_button])
    
    def get_tab_name(self) -> str:
        """Return the tab display name."""
        return "HDsEMG"


class FeaturesTab(BaseTab):
    """
    Features tab implementation following the BaseTab interface.
    Displays feature extraction results with controls.
    """

    def __init__(self, parent=None):
        self.feature_scroll_layout = None
        self.feature_controls_button = None
        super().__init__(parent)
    
    def create_content_area(self) -> QtWidgets.QWidget:
        """Create the scrollable area for feature plots."""
        scroll_area, scroll_widget, self.feature_scroll_layout = self.create_scroll_area()
        return scroll_area
    
    def create_control_panel(self) -> QtWidgets.QWidget:
        """Create control panel with feature controls."""
        self.feature_controls_button = QtWidgets.QPushButton("Feature Controls")

        return self.create_control_panel_base([self.feature_controls_button])

    def connect_signals(self, window):
        self.feature_controls_button.clicked.connect(window.open_feature_controls)

    def get_tab_name(self) -> str:
        """Return the tab display name."""
        return "Features"
