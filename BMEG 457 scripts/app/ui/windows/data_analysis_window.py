"""Window for analyzing recorded EMG data from CSV files."""

from PyQt5 import QtWidgets, QtCore, QtGui
import os

from app.data.csv_loader import CSVDataLoader
from app.managers.analysis_track_manager import AnalysisTrackManager
from app.managers.time_navigation_controller import TimeNavigationController


class DataAnalysisWindow(QtWidgets.QWidget):
    """Window for analyzing recorded EMG data from CSV files."""

    def __init__(self):
        super().__init__()

        self.csv_loader = CSVDataLoader()
        self.track_manager = None
        self.time_controller = TimeNavigationController()
        self.total_duration = 0.0

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

        # Time/window controls row
        self._create_time_controls()

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

    def _create_time_controls(self):
        """Create time navigation and window controls."""
        time_row = QtWidgets.QWidget()
        time_layout = QtWidgets.QHBoxLayout(time_row)

        # Go to start button
        self.start_button = QtWidgets.QPushButton("<<")
        self.start_button.setMaximumWidth(40)
        self.start_button.setToolTip("Go to start")
        time_layout.addWidget(self.start_button)

        # Step back button
        self.step_back_button = QtWidgets.QPushButton("<")
        self.step_back_button.setMaximumWidth(30)
        self.step_back_button.setToolTip("Step back")
        time_layout.addWidget(self.step_back_button)

        # Time slider
        self.time_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(1000)  # 0.1% resolution
        self.time_slider.setValue(0)
        time_layout.addWidget(self.time_slider, stretch=1)

        # Step forward button
        self.step_forward_button = QtWidgets.QPushButton(">")
        self.step_forward_button.setMaximumWidth(30)
        self.step_forward_button.setToolTip("Step forward")
        time_layout.addWidget(self.step_forward_button)

        # Go to end button
        self.end_button = QtWidgets.QPushButton(">>")
        self.end_button.setMaximumWidth(40)
        self.end_button.setToolTip("Go to end")
        time_layout.addWidget(self.end_button)

        time_layout.addSpacing(20)

        # Position label
        self.position_label = QtWidgets.QLabel("Position: 0.00s / 0.00s")
        time_layout.addWidget(self.position_label)

        time_layout.addSpacing(20)

        # Window duration input
        time_layout.addWidget(QtWidgets.QLabel("Window (s):"))
        self.window_input = QtWidgets.QLineEdit("5")
        self.window_input.setMaximumWidth(60)
        self.window_input.setValidator(QtGui.QDoubleValidator(0.1, 1000, 2))
        time_layout.addWidget(self.window_input)

        self.apply_window_button = QtWidgets.QPushButton("Apply")
        self.apply_window_button.setMaximumWidth(60)
        time_layout.addWidget(self.apply_window_button)

        self.main_layout.addWidget(time_row)

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

        # Channel selection section
        ctrl_layout.addWidget(QtWidgets.QLabel("Select Channels (max 2):"))

        # Channel 1 selector
        ch1_layout = QtWidgets.QHBoxLayout()
        ch1_layout.addWidget(QtWidgets.QLabel("Ch 1:"))
        self.channel1_combo = QtWidgets.QComboBox()
        self.channel1_combo.addItem("None")
        ch1_layout.addWidget(self.channel1_combo)
        ctrl_layout.addLayout(ch1_layout)

        # Channel 2 selector
        ch2_layout = QtWidgets.QHBoxLayout()
        ch2_layout.addWidget(QtWidgets.QLabel("Ch 2:"))
        self.channel2_combo = QtWidgets.QComboBox()
        self.channel2_combo.addItem("None")
        ch2_layout.addWidget(self.channel2_combo)
        ctrl_layout.addLayout(ch2_layout)

        # Info label
        self.channels_info_label = QtWidgets.QLabel("Load a file to select channels")
        self.channels_info_label.setStyleSheet("color: gray; font-size: 11px;")
        ctrl_layout.addWidget(self.channels_info_label)

        ctrl_layout.addSpacing(20)

        # Processing section
        ctrl_layout.addWidget(QtWidgets.QLabel("Processing:"))

        # Rectification checkbox
        self.rectify_checkbox = QtWidgets.QCheckBox("Rectify")
        ctrl_layout.addWidget(self.rectify_checkbox)

        ctrl_layout.addSpacing(10)

        # Envelope type selection
        ctrl_layout.addWidget(QtWidgets.QLabel("Envelope:"))

        self.envelope_group = QtWidgets.QButtonGroup(self)
        self.envelope_none_radio = QtWidgets.QRadioButton("None")
        self.envelope_rms_radio = QtWidgets.QRadioButton("RMS")
        self.envelope_lowpass_radio = QtWidgets.QRadioButton("Lowpass")

        self.envelope_none_radio.setChecked(True)
        self.envelope_group.addButton(self.envelope_none_radio, 0)
        self.envelope_group.addButton(self.envelope_rms_radio, 1)
        self.envelope_group.addButton(self.envelope_lowpass_radio, 2)

        ctrl_layout.addWidget(self.envelope_none_radio)
        ctrl_layout.addWidget(self.envelope_rms_radio)
        ctrl_layout.addWidget(self.envelope_lowpass_radio)

        ctrl_layout.addSpacing(10)

        # RMS window size input
        rms_layout = QtWidgets.QHBoxLayout()
        rms_layout.addWidget(QtWidgets.QLabel("RMS Window:"))
        self.rms_window_input = QtWidgets.QLineEdit("50")
        self.rms_window_input.setMaximumWidth(60)
        self.rms_window_input.setValidator(QtGui.QIntValidator(1, 10000))
        rms_layout.addWidget(self.rms_window_input)
        rms_layout.addWidget(QtWidgets.QLabel("samples"))
        ctrl_layout.addLayout(rms_layout)

        # Lowpass cutoff input
        lp_layout = QtWidgets.QHBoxLayout()
        lp_layout.addWidget(QtWidgets.QLabel("LP Cutoff:"))
        self.lowpass_cutoff_input = QtWidgets.QLineEdit("10")
        self.lowpass_cutoff_input.setMaximumWidth(60)
        self.lowpass_cutoff_input.setValidator(QtGui.QDoubleValidator(0.1, 1000, 1))
        lp_layout.addWidget(self.lowpass_cutoff_input)
        lp_layout.addWidget(QtWidgets.QLabel("Hz"))
        ctrl_layout.addLayout(lp_layout)

        ctrl_layout.addSpacing(10)

        # Apply processing button
        self.apply_processing_button = QtWidgets.QPushButton("Apply Processing")
        ctrl_layout.addWidget(self.apply_processing_button)

        ctrl_layout.addStretch()
        content_layout.addWidget(control_panel, stretch=0)

        self.main_layout.addWidget(content_widget)

    def _connect_signals(self):
        """Connect all UI signals to handlers."""
        # File controls
        self.open_file_button.clicked.connect(self.open_file_dialog)

        # Time navigation
        self.start_button.clicked.connect(self._go_to_start)
        self.step_back_button.clicked.connect(self._step_back)
        self.step_forward_button.clicked.connect(self._step_forward)
        self.end_button.clicked.connect(self._go_to_end)
        self.time_slider.valueChanged.connect(self._on_slider_changed)

        # Window controls
        self.apply_window_button.clicked.connect(self._apply_window_duration)
        self.window_input.returnPressed.connect(self._apply_window_duration)

        # Channel selectors
        self.channel1_combo.currentIndexChanged.connect(self._on_channel_selection_changed)
        self.channel2_combo.currentIndexChanged.connect(self._on_channel_selection_changed)

        # Processing controls
        self.apply_processing_button.clicked.connect(self._apply_processing)

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

        self.total_duration = self.csv_loader.get_duration()
        channels = min(64, self.csv_loader.get_channel_count())
        samples = self.csv_loader.get_sample_count()
        sample_rate = self.csv_loader.sample_rate

        self.file_info_label.setText(
            f"Duration: {self.total_duration:.2f}s | {channels} channels | "
            f"{samples} samples | {sample_rate:.0f} Hz"
        )

        # Initialize track manager
        self.track_manager = AnalysisTrackManager(self.scroll_layout)
        self.track_manager.initialize_tracks_from_csv(self.csv_loader)

        # Populate channel selectors
        self._populate_channel_selectors(channels)

        # Set initial window duration (5 seconds or full duration if shorter)
        initial_window = min(5.0, self.total_duration)
        self.window_input.setText(str(initial_window))
        self.time_controller.reset(self.total_duration, initial_window)

        # Apply initial view
        self._update_view()

        # Update info
        self.channels_info_label.setText("Select up to 2 channels to display")
        self.channels_info_label.setStyleSheet("color: orange; font-size: 11px;")

    def _populate_channel_selectors(self, num_channels: int):
        """Populate channel selector dropdowns."""
        # Block signals while populating
        self.channel1_combo.blockSignals(True)
        self.channel2_combo.blockSignals(True)

        self.channel1_combo.clear()
        self.channel2_combo.clear()

        self.channel1_combo.addItem("None")
        self.channel2_combo.addItem("None")

        for i in range(num_channels):
            self.channel1_combo.addItem(f"Channel {i + 1}")
            self.channel2_combo.addItem(f"Channel {i + 1}")

        self.channel1_combo.blockSignals(False)
        self.channel2_combo.blockSignals(False)

    def _on_channel_selection_changed(self):
        """Handle channel selection changes."""
        if self.track_manager is None:
            return

        selected = []

        # Get channel 1 selection
        ch1_idx = self.channel1_combo.currentIndex()
        if ch1_idx > 0:  # 0 is "None"
            selected.append(ch1_idx - 1)

        # Get channel 2 selection
        ch2_idx = self.channel2_combo.currentIndex()
        if ch2_idx > 0:  # 0 is "None"
            selected.append(ch2_idx - 1)

        self.track_manager.set_selected_channels(selected)
        self.track_manager.draw_all_tracks()

        # Update info label
        if len(selected) == 0:
            self.channels_info_label.setText("No channels selected")
            self.channels_info_label.setStyleSheet("color: orange; font-size: 11px;")
        else:
            ch_names = [f"Ch {ch + 1}" for ch in selected]
            self.channels_info_label.setText(f"Displaying: {', '.join(ch_names)}")
            self.channels_info_label.setStyleSheet("color: green; font-size: 11px;")

    def _apply_processing(self):
        """Apply signal processing settings to the track."""
        if self.track_manager is None:
            return

        # Get rectification setting
        rectify = self.rectify_checkbox.isChecked()

        # Get envelope type
        if self.envelope_rms_radio.isChecked():
            envelope_type = 'rms'
        elif self.envelope_lowpass_radio.isChecked():
            envelope_type = 'lowpass'
        else:
            envelope_type = 'none'

        # Get RMS window size
        try:
            rms_window = int(self.rms_window_input.text())
            if rms_window < 1:
                rms_window = 1
        except ValueError:
            rms_window = 50

        # Get lowpass cutoff
        try:
            lowpass_cutoff = float(self.lowpass_cutoff_input.text())
            if lowpass_cutoff <= 0:
                lowpass_cutoff = 10
        except ValueError:
            lowpass_cutoff = 10

        # Apply processing
        self.track_manager.set_processing(rectify, envelope_type, rms_window, lowpass_cutoff)

    def _apply_window_duration(self):
        """Apply the window duration from input field."""
        try:
            duration = float(self.window_input.text())
            if duration <= 0:
                duration = 1.0
            if duration > self.total_duration:
                duration = self.total_duration

            self.time_controller.set_window_duration(duration)
            self._update_view()
        except ValueError:
            pass

    def _go_to_start(self):
        """Go to start of recording."""
        self.time_controller.go_to_start()
        self._update_view()

    def _go_to_end(self):
        """Go to end of recording."""
        self.time_controller.go_to_end()
        self._update_view()

    def _step_back(self):
        """Step back by 10% of window."""
        self.time_controller.scroll_left()
        self._update_view()

    def _step_forward(self):
        """Step forward by 10% of window."""
        self.time_controller.scroll_right()
        self._update_view()

    def _on_slider_changed(self, value: int):
        """Handle time slider position changes."""
        normalized = value / 1000.0
        self.time_controller.set_normalized_position(normalized)
        self._update_view(update_slider=False)

    def _update_view(self, update_slider: bool = True):
        """Update the view based on current time controller state."""
        if self.track_manager is None:
            return

        start_time = self.time_controller.get_current_start()
        duration = self.time_controller.get_current_duration()

        # Update track
        self.track_manager.set_view_window(start_time, duration)
        self.track_manager.draw_all_tracks()

        # Update position label
        self.position_label.setText(
            f"Position: {start_time:.2f}s / {self.total_duration:.2f}s"
        )

        # Update slider
        if update_slider:
            self.time_slider.blockSignals(True)
            normalized = self.time_controller.get_normalized_position()
            self.time_slider.setValue(int(normalized * 1000))
            self.time_slider.blockSignals(False)

    def closeEvent(self, event):
        """Handle window close event."""
        event.accept()
