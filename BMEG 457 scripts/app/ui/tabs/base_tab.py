"""
Base tab interface for standardized tab layout.
All tabs should inherit from BaseTab to ensure consistent UI structure.
"""
from PyQt5 import QtWidgets, QtCore
from abc import ABC, abstractmethod
from ...core.config import Config


class BaseTab(QtWidgets.QWidget, ABC):
    """
    Abstract base class for standardized tab layout.
    
    Layout structure:
    - Top control bar (inherited from parent window): Calibrate, Stream, Record buttons
    - Content area (left side, stretch=3): Main visualization/content
    - Control panel (right side, stretch=0): Tab-specific controls
    
    Subclasses must implement:
    - create_content_area(): Returns the main content widget
    - create_control_panel(): Returns the control panel widget with tab-specific buttons
    - get_tab_name(): Returns the display name for the tab
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_layout()
    
    def _setup_layout(self):
        """
        Sets up the standardized horizontal layout.
        Left: content area (Config.CONTENT_STRETCH)
        Right: control panel (Config.PANEL_STRETCH)
        """
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Left side: Content area (scrollable by default)
        self.content_area = self.create_content_area()
        main_layout.addWidget(self.content_area, stretch=Config.CONTENT_STRETCH)
        
        # Right side: Control panel
        self.control_panel = self.create_control_panel()
        main_layout.addWidget(self.control_panel, stretch=Config.PANEL_STRETCH)
    
    @abstractmethod
    def create_content_area(self) -> QtWidgets.QWidget:
        """
        Create and return the main content area widget.
        This is typically a scroll area or plot widget.
        
        Returns:
            QtWidgets.QWidget: The content area widget
        """
        pass
    
    @abstractmethod
    def create_control_panel(self) -> QtWidgets.QWidget:
        """
        Create and return the right-side control panel widget.
        Add all tab-specific buttons and controls here.
        
        Returns:
            QtWidgets.QWidget: The control panel widget
        """
        pass
    
    @abstractmethod
    def get_tab_name(self) -> str:
        """
        Get the display name for this tab.
        
        Returns:
            str: The tab name to display
        """
        pass
    
    def create_scroll_area(self) -> tuple[QtWidgets.QScrollArea, QtWidgets.QWidget, QtWidgets.QVBoxLayout]:
        """
        Utility method to create a standard scroll area setup.
        
        Returns:
            tuple: (scroll_area, scroll_widget, scroll_layout)
        """
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
        
        scroll_area.setWidget(scroll_widget)
        
        return scroll_area, scroll_widget, scroll_layout
    
    def create_control_panel_base(self, buttons: list[QtWidgets.QPushButton] = None) -> QtWidgets.QWidget:
        """
        Utility method to create a standard control panel with buttons.
        
        Args:
            buttons: List of QPushButton widgets to add to the panel
            
        Returns:
            QtWidgets.QWidget: The control panel widget
        """
        panel = QtWidgets.QWidget()
        panel.setMaximumWidth(200)  # Standard width for control panels
        layout = QtWidgets.QVBoxLayout(panel)
        
        if buttons:
            for button in buttons:
                layout.addWidget(button)
        
        layout.addStretch()
        
        return panel


class EmptyTab(BaseTab):
    """
    Example/template tab implementation.
    Use this as a starting point for new tabs.
    """
    
    def __init__(self, parent=None, tab_name="New Tab"):
        self._tab_name = tab_name
        super().__init__(parent)
    
    def create_content_area(self) -> QtWidgets.QWidget:
        """Create the main content area."""
        scroll_area, scroll_widget, scroll_layout = self.create_scroll_area()
        
        # Add your content here
        label = QtWidgets.QLabel(f"Content for {self._tab_name}")
        label.setAlignment(QtCore.Qt.AlignCenter)
        scroll_layout.addWidget(label)
        scroll_layout.addStretch()
        
        return scroll_area
    
    def create_control_panel(self) -> QtWidgets.QWidget:
        """Create the control panel with tab-specific buttons."""
        # Create buttons
        example_button = QtWidgets.QPushButton("Example Control")
        
        # Use utility method to create panel
        return self.create_control_panel_base([example_button])
    
    def get_tab_name(self) -> str:
        """Return the tab display name."""
        return self._tab_name
