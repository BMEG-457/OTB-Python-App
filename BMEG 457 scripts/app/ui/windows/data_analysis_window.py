"""Window for analyzing recorded EMG data from CSV files."""

from PyQt5 import QtWidgets, QtCore
import os

from app.data.csv_loader import CSVDataLoader
from app.managers.analysis_track_manager import AnalysisTrackManager
from app.ui.dialogs.dialogs import ChannelSelectorDialog


class DataAnalysisWindow(QtWidgets.QWidget):
    """Window for analyzing recorded EMG data from CSV files."""

    def __init__(self):
        super().__init__()

        self.csv_loader = CSVDataLoader()
        self.track_manager = None

        self.setWindowTitle("Data Analysis")
        self.setGeometry(100, 100, 1200, 800)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Create the UI layout."""
        self.main_layout = QtWidgets.QVBoxLayout(self)

        # Back button row
        self._create_back_button_row()

        # File controls row
        self._create_file_controls()

        # Main content area with plot and controls
        self._create_main_content()

    def _create_back_button_row(self):
        """Create back button row."""
        back_row = QtWidgets.QWidget()
        back_layout = QtWidgets.QHBoxLayout(back_row)
        self.back_button = QtWidgets.QPushButton("← Back")
        self.back_button.setMaximumWidth(100)
        back_layout.addWidget(self.back_button)
        back_layout.addStretch()
        self.main_layout.addWidget(back_row)

    def _create_file_controls(self):
        """Create file loading controls."""
        file_row = QtWidgets.QWidget()
        file_layout = QtWidgets.QHBoxLayout(file_row)

        # Open file button
        file_layout.addWidget(QtWidgets.QLabel("File:"))
        self.open_file_button = QtWidgets.QPushButton("Open File")
        file_layout.addWidget(self.open_file_button)

        # Filename label
        self.filename_label = QtWidgets.QLabel("No file loaded")
        self.filename_label.setStyleSheet("color: gray;")
        file_layout.addWidget(self.filename_label)

        file_layout.addSpacing(20)

        # File info label
        self.file_info_label = QtWidgets.QLabel("")
        file_layout.addWidget(self.file_info_label)

        file_layout.addStretch()
        self.main_layout.addWidget(file_row)

    def _create_main_content(self):
        """Create main content area with plot and control panel."""
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QHBoxLayout(content_widget)

        # Scroll area for the track
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.scroll_area.setWidget(self.scroll_widget)
        content_layout.addWidget(self.scroll_area, stretch=3)

        # Right-side control panel
        control_panel = QtWidgets.QWidget()
        ctrl_layout = QtWidgets.QVBoxLayout(control_panel)

        self.select_channels_button = QtWidgets.QPushButton("Select Channels")
        ctrl_layout.addWidget(self.select_channels_button)

        # Label showing selected channels count
        self.channels_info_label = QtWidgets.QLabel("No channels selected")
        self.channels_info_label.setStyleSheet("color: gray; font-size: 11px;")
        ctrl_layout.addWidget(self.channels_info_label)

        ctrl_layout.addStretch()
        content_layout.addWidget(control_panel, stretch=0)

        self.main_layout.addWidget(content_widget)

    def _connect_signals(self):
        """Connect all UI signals to handlers."""
        # File controls
        self.open_file_button.clicked.connect(self.open_file_dialog)

        # Channel selection
        self.select_channels_button.clicked.connect(self.open_channel_selector)

    def open_file_dialog(self):
        """Show file picker for CSV files."""
        # Default to recordings directory
        recordings_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), 'recordings')

        if not os.path.exists(recordings_dir):
            recordings_dir = ""

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Recording File",
            recordings_dir,
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            self.load_csv_file(file_path)

    def load_csv_file(self, file_path: str):
        """Load a CSV file and initialize visualization."""
        # Load CSV
        if not self.csv_loader.load_file(file_path):
            QtWidgets.QMessageBox.critical(
                self, "Load Error",
                f"Failed to load file: {file_path}"
            )
            return

        # Update file info labels
        filename = os.path.basename(file_path)
        self.filename_label.setText(filename)
        self.filename_label.setStyleSheet("color: black;")

        duration = self.csv_loader.get_duration()
        channels = min(64, self.csv_loader.get_channel_count())
        samples = self.csv_loader.get_sample_count()
        sample_rate = self.csv_loader.sample_rate

        self.file_info_label.setText(
            f"Duration: {duration:.2f}s | {channels} channels | "
            f"{samples} samples | {sample_rate:.0f} Hz"
        )

        # Initialize track manager
        self.track_manager = AnalysisTrackManager(self.scroll_layout)
        self.track_manager.initialize_tracks_from_csv(self.csv_loader)

        # Set view to show ALL data at once (full duration)
        self.track_manager.set_view_window(0, duration)

        # No channels selected initially
        self.channels_info_label.setText("No channels selected - click Select Channels")
        self.channels_info_label.setStyleSheet("color: orange; font-size: 11px;")

        # Draw (will show empty plot since no channels are visible)
        self.track_manager.draw_all_tracks()

        # Prompt user to select channels
        QtWidgets.QMessageBox.information(
            self, "File Loaded",
            f"Loaded {channels} channels.\n\nClick 'Select Channels' to choose which channels to display."
        )

    def open_channel_selector(self):
        """Open channel selection dialog."""
        if self.track_manager is None:
            QtWidgets.QMessageBox.warning(
                self, "No Data",
                "Please load a CSV file first."
            )
            return

        num = self.track_manager.get_hdsemg_channel_count()
        current = self.track_manager.get_visible_channels()

        dlg = ChannelSelectorDialog(self, num, selected=current)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            sel = dlg.selected_indices()
            self.track_manager.set_visible_channels(sel)
            self.track_manager.draw_all_tracks()

            # Update channels info label
            if len(sel) == 0:
                self.channels_info_label.setText("No channels selected")
                self.channels_info_label.setStyleSheet("color: orange; font-size: 11px;")
            else:
                self.channels_info_label.setText(f"{len(sel)} channel(s) selected")
                self.channels_info_label.setStyleSheet("color: green; font-size: 11px;")

    def closeEvent(self, event):
        """Handle window close event."""
        event.accept()
