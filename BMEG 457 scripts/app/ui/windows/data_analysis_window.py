"""Window for analyzing recorded EMG data from CSV files."""

from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import csv
import os
import numpy as np
from datetime import datetime

from app.core.paths import get_recordings_dir, get_data_dir
from app.data.csv_loader import CSVDataLoader
from app.managers.analysis_track_manager import AnalysisTrackManager
from app.managers.time_navigation_controller import TimeNavigationController
from app.ui.panels.data_viewing_panel import DataViewingPanel
from app.ui.panels.features_panel import FeaturesPanel
from app.processing.features import (
    compute_tkeo_activation_timing,
    compute_burst_duration,
    compute_bilateral_symmetry,
    compute_fatigue,
    compute_centroid_shift,
    compute_spatial_nonuniformity,
)


class DataAnalysisWindow(QtWidgets.QWidget):
    """Window for analyzing recorded EMG data from CSV files."""

    def __init__(self):
        super().__init__()

        self.csv_loader = CSVDataLoader()
        self.track_manager = None
        self.time_controller = TimeNavigationController()
        self.total_duration = 0.0

        # Last feature analysis results for export
        self._last_feature_results = []   # list of (ch_idx, result) tuples
        self._last_feature_type = None    # 'tkeo' | 'burst' | 'bilateral' | 'fatigue'
        self._last_bilateral_meta = {}    # file/channel names for bilateral symmetry export

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
        """Create main content area with shared plot, tabbed control panels, and results panel."""
        # Vertical splitter: plot area on top, results panel on bottom
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        # Top section: plot + control tabs side by side
        top_widget = QtWidgets.QWidget()
        top_layout = QtWidgets.QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # Shared scroll area for the plot (visible in all tabs)
        self._create_shared_plot_area(top_layout)

        # Tab widget for control panels only (right side)
        self.content_tabs = QtWidgets.QTabWidget()
        self.content_tabs.setMaximumWidth(250)

        # Create control panels as tabs
        self.data_viewing_panel = DataViewingPanel()
        self.content_tabs.addTab(self.data_viewing_panel, "Data Viewing")

        self.features_panel = FeaturesPanel()
        self.content_tabs.addTab(self.features_panel, "Features")

        top_layout.addWidget(self.content_tabs, stretch=0)
        splitter.addWidget(top_widget)

        # Bottom section: results panel
        self._create_results_panel(splitter)

        # Set initial split ratio (plot gets ~80%, results ~20%)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        self.main_layout.addWidget(splitter)

    def _create_shared_plot_area(self, parent_layout):
        """Create the shared scroll area for plots (visible in all tabs)."""
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.scroll_area.setWidget(self.scroll_widget)
        parent_layout.addWidget(self.scroll_area, stretch=3)

    def _create_results_panel(self, parent_splitter):
        """Create the bottom results panel."""
        results_widget = QtWidgets.QWidget()
        results_layout = QtWidgets.QVBoxLayout(results_widget)
        results_layout.setContentsMargins(5, 2, 5, 2)

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.addWidget(QtWidgets.QLabel("Results"))
        self.clear_results_button = QtWidgets.QPushButton("Clear")
        self.clear_results_button.setMaximumWidth(60)
        self.clear_results_button.clicked.connect(lambda: self.feature_results_text.clear())
        header_layout.addStretch()
        header_layout.addWidget(self.clear_results_button)
        results_layout.addLayout(header_layout)

        self.feature_results_text = QtWidgets.QTextEdit()
        self.feature_results_text.setReadOnly(True)
        self.feature_results_text.setStyleSheet(
            "QTextEdit { font-family: Consolas, monospace; font-size: 11px; "
            "background-color: #1e1e1e; color: #d4d4d4; }"
        )
        self.feature_results_text.setPlaceholderText("Feature results will appear here...")
        results_layout.addWidget(self.feature_results_text)

        parent_splitter.addWidget(results_widget)

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
        self.data_viewing_panel.channel1_combo.currentIndexChanged.connect(self._on_channel_selection_changed)
        self.data_viewing_panel.channel2_combo.currentIndexChanged.connect(self._on_channel_selection_changed)

        # Processing controls
        self.data_viewing_panel.apply_processing_button.clicked.connect(self._apply_processing)

        # Feature controls
        self.features_panel.activation_timings_button.clicked.connect(self._on_activation_timings)
        self.features_panel.burst_duration_button.clicked.connect(self._on_burst_duration)
        self.features_panel.bilateral_symmetry_button.clicked.connect(self._on_bilateral_symmetry)
        self.features_panel.fatigue_analysis_button.clicked.connect(self._on_fatigue_analysis)
        self.features_panel.centroid_shift_button.clicked.connect(self._on_centroid_shift)
        self.features_panel.spatial_nonuniformity_button.clicked.connect(self._on_spatial_nonuniformity)
        self.features_panel.export_button.clicked.connect(self._on_export_results)

    def open_file_dialog(self):
        """Show file picker for CSV files."""
        # Default to recordings directory
        recordings_dir = get_recordings_dir()

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
        self.data_viewing_panel.channels_info_label.setText("Select up to 2 channels to display")
        self.data_viewing_panel.channels_info_label.setStyleSheet("color: orange; font-size: 11px;")

    def _populate_channel_selectors(self, num_channels: int):
        """Populate channel selector dropdowns."""
        dvp = self.data_viewing_panel

        # Block signals while populating
        dvp.channel1_combo.blockSignals(True)
        dvp.channel2_combo.blockSignals(True)

        dvp.channel1_combo.clear()
        dvp.channel2_combo.clear()

        dvp.channel1_combo.addItem("None")
        dvp.channel2_combo.addItem("None")

        for i in range(num_channels):
            dvp.channel1_combo.addItem(f"Channel {i + 1}")
            dvp.channel2_combo.addItem(f"Channel {i + 1}")

        dvp.channel1_combo.blockSignals(False)
        dvp.channel2_combo.blockSignals(False)

    def _on_channel_selection_changed(self):
        """Handle channel selection changes."""
        if self.track_manager is None:
            return

        dvp = self.data_viewing_panel
        selected = []

        # Get channel 1 selection
        ch1_idx = dvp.channel1_combo.currentIndex()
        if ch1_idx > 0:  # 0 is "None"
            selected.append(ch1_idx - 1)

        # Get channel 2 selection
        ch2_idx = dvp.channel2_combo.currentIndex()
        if ch2_idx > 0:  # 0 is "None"
            selected.append(ch2_idx - 1)

        self.track_manager.set_selected_channels(selected)
        self.track_manager.draw_all_tracks()

        # Update info label
        if len(selected) == 0:
            dvp.channels_info_label.setText("No channels selected")
            dvp.channels_info_label.setStyleSheet("color: orange; font-size: 11px;")
        else:
            ch_names = [f"Ch {ch + 1}" for ch in selected]
            dvp.channels_info_label.setText(f"Displaying: {', '.join(ch_names)}")
            dvp.channels_info_label.setStyleSheet("color: green; font-size: 11px;")

    def _apply_processing(self):
        """Apply signal processing settings to the track."""
        if self.track_manager is None:
            return

        dvp = self.data_viewing_panel

        # Get rectification setting
        rectify = dvp.rectify_checkbox.isChecked()

        # Get envelope type
        if dvp.envelope_rms_radio.isChecked():
            envelope_type = 'rms'
        elif dvp.envelope_lowpass_radio.isChecked():
            envelope_type = 'lowpass'
        else:
            envelope_type = 'none'

        # Get RMS window size
        try:
            rms_window = int(dvp.rms_window_input.text())
            if rms_window < 1:
                rms_window = 1
        except ValueError:
            rms_window = 50

        # Get lowpass cutoff
        try:
            lowpass_cutoff = float(dvp.lowpass_cutoff_input.text())
            if lowpass_cutoff <= 0:
                lowpass_cutoff = 10
        except ValueError:
            lowpass_cutoff = 10

        # Apply processing
        self.track_manager.set_processing(rectify, envelope_type, rms_window, lowpass_cutoff)

    def _on_activation_timings(self):
        """Compute TKEO activation timings on selected channel(s) and add feature tracks."""
        if self.csv_loader is None or not self.csv_loader.is_loaded():
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        if self.track_manager is None:
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        selected = self.track_manager.get_selected_channels()
        if len(selected) == 0:
            QtWidgets.QMessageBox.warning(
                self, "No Channel Selected",
                "Please select at least one channel in the Data Viewing tab."
            )
            return

        # Clear previous feature tracks and results
        self.track_manager.remove_feature_tracks()
        self.feature_results_text.clear()

        raw_data = self.csv_loader.data
        timestamps = self.csv_loader.timestamps
        sample_rate = self.csv_loader.sample_rate
        base_time = timestamps[0]

        self._last_feature_results = []
        self._last_feature_type = 'tkeo'
        self._last_bilateral_meta = {}

        errors = []
        results_text_parts = []
        for ch_idx in selected:
            ch_signal = raw_data[ch_idx, :]

            result = compute_tkeo_activation_timing(
                raw_signal=ch_signal,
                timestamps=timestamps,
                sample_rate=sample_rate,
            )

            if result is None:
                errors.append(f"Channel {ch_idx + 1}")
                continue

            self._last_feature_results.append((ch_idx, result))

            title = f"TKEO Activation - Ch {ch_idx + 1} ({len(result.onset_times)} onsets)"
            self.track_manager.add_feature_track(
                title=title,
                timestamps=result.timestamps,
                data_1d=result.tkeo_envelope,
                sample_rate=result.sample_rate,
                onset_times=result.onset_times,
                detection_threshold=result.detection_threshold,
                backtrack_threshold=result.backtrack_threshold,
            )

            # Build results text for this channel
            lines = [f"Channel {ch_idx + 1}: {len(result.onset_times)} onsets"]
            for i, t in enumerate(result.onset_times):
                relative_t = t - base_time
                lines.append(f"  #{i + 1}  {relative_t:.3f}s")
            results_text_parts.append("\n".join(lines))

        if results_text_parts:
            self.feature_results_text.setText("\n\n".join(results_text_parts))
        else:
            self.feature_results_text.setText("No onsets detected.")

        if errors:
            QtWidgets.QMessageBox.warning(
                self, "Processing Warning",
                f"TKEO computation failed for: {', '.join(errors)}.\n"
                "The signal may be too short or contain invalid data."
            )

        self._update_view()

    def _on_burst_duration(self):
        """Compute burst duration statistics on selected channel(s)."""
        if self.csv_loader is None or not self.csv_loader.is_loaded():
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        if self.track_manager is None:
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        selected = self.track_manager.get_selected_channels()
        if len(selected) == 0:
            QtWidgets.QMessageBox.warning(
                self, "No Channel Selected",
                "Please select at least one channel in the Data Viewing tab."
            )
            return

        self.feature_results_text.clear()

        raw_data = self.csv_loader.data
        timestamps = self.csv_loader.timestamps
        sample_rate = self.csv_loader.sample_rate

        self._last_feature_results = []
        self._last_feature_type = 'burst'
        self._last_bilateral_meta = {}

        errors = []
        results_text_parts = []
        for ch_idx in selected:
            ch_signal = raw_data[ch_idx, :]

            result = compute_burst_duration(
                raw_signal=ch_signal,
                timestamps=timestamps,
                sample_rate=sample_rate,
            )

            if result is None:
                errors.append(f"Channel {ch_idx + 1}")
                continue

            self._last_feature_results.append((ch_idx, result))

            lines = [
                f"Channel {ch_idx + 1}: Burst Duration Analysis",
                f"  Number of bursts: {result.num_bursts}",
                f"  Average burst duration: {result.avg_duration:.3f} s",
                f"  Burst duration variance (std): {result.std_duration:.3f} s",
            ]
            results_text_parts.append("\n".join(lines))

        if results_text_parts:
            self.feature_results_text.setText("\n\n".join(results_text_parts))
        else:
            self.feature_results_text.setText("No bursts detected.")

        if errors:
            QtWidgets.QMessageBox.warning(
                self, "Processing Warning",
                f"Burst duration computation failed for: {', '.join(errors)}.\n"
                "The signal may be too short or contain invalid data."
            )

    def _on_bilateral_symmetry(self):
        """Compute bilateral symmetry between selected channel and a channel from a second file."""
        if self.csv_loader is None or not self.csv_loader.is_loaded():
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        if self.track_manager is None:
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        selected = self.track_manager.get_selected_channels()
        if len(selected) == 0:
            QtWidgets.QMessageBox.warning(
                self, "No Channel Selected",
                "Please select at least one channel in the Data Viewing tab."
            )
            return

        ch1_idx = selected[0]

        # Open file dialog for the second CSV
        recordings_dir = get_recordings_dir()
        if not os.path.exists(recordings_dir):
            recordings_dir = ""

        file_path_2, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Second Recording File (for comparison)",
            recordings_dir,
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path_2:
            return

        # Load the second file with a temporary loader
        loader_2 = CSVDataLoader()
        if not loader_2.load_file(file_path_2):
            QtWidgets.QMessageBox.critical(
                self, "Load Error",
                f"Failed to load second file: {file_path_2}"
            )
            return

        # Channel selection for file 2
        num_channels_2 = loader_2.get_channel_count()
        if num_channels_2 == 0:
            QtWidgets.QMessageBox.warning(self, "No Channels", "Second file contains no channels.")
            return

        channel_names_2 = [f"Channel {i + 1}" for i in range(num_channels_2)]
        ch2_name, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Select Channel from File 2",
            f"File: {os.path.basename(file_path_2)}\n"
            f"({num_channels_2} channels, {loader_2.sample_rate:.0f} Hz, "
            f"{loader_2.get_duration():.2f}s)\n\n"
            f"Comparing against: Channel {ch1_idx + 1} from File 1\n\n"
            f"Select channel:",
            channel_names_2,
            0,
            False
        )

        if not ok:
            return

        ch2_idx = channel_names_2.index(ch2_name)

        # Extract signals
        signal_1 = self.csv_loader.data[ch1_idx, :]
        timestamps_1 = self.csv_loader.timestamps
        sample_rate_1 = self.csv_loader.sample_rate

        signal_2 = loader_2.data[ch2_idx, :]
        timestamps_2 = loader_2.timestamps
        sample_rate_2 = loader_2.sample_rate

        # Compute
        self.track_manager.remove_feature_tracks()
        self.feature_results_text.clear()

        self._last_feature_results = []
        self._last_feature_type = 'bilateral'
        self._last_bilateral_meta = {}

        result = compute_bilateral_symmetry(
            signal_1=signal_1,
            timestamps_1=timestamps_1,
            sample_rate_1=sample_rate_1,
            signal_2=signal_2,
            timestamps_2=timestamps_2,
            sample_rate_2=sample_rate_2,
        )

        if result is None:
            QtWidgets.QMessageBox.warning(
                self, "Computation Failed",
                "Bilateral symmetry computation failed.\n"
                "The signals may be too short or contain invalid data."
            )
            return

        self._last_feature_results = [(ch1_idx, result)]
        self._last_bilateral_meta = {
            'file1': os.path.basename(self.csv_loader.file_path),
            'ch1_idx': ch1_idx,
            'file2': os.path.basename(file_path_2),
            'ch2_idx': ch2_idx,
        }

        # Add feature track
        file1_name = os.path.basename(self.csv_loader.file_path)
        file2_name = os.path.basename(file_path_2)

        title = (
            f"Bilateral Symmetry - Ch{ch1_idx + 1} ({file1_name}) "
            f"vs Ch{ch2_idx + 1} ({file2_name})"
        )

        feature_track = self.track_manager.add_feature_track(
            title=title,
            timestamps=result.timestamps,
            data_1d=result.symmetry_index,
            sample_rate=result.sample_rate,
        )

        # Add reference line at y=0 (perfect symmetry)
        zero_line = pg.InfiniteLine(
            pos=0.0, angle=0,
            pen=pg.mkPen(color=(255, 255, 255, 100), width=1, style=QtCore.Qt.DashLine),
        )
        feature_track.plot_widget.addItem(zero_line)
        feature_track.plot_widget.setYRange(-1.0, 1.0)

        # Display results
        lines = [
            "=== Bilateral Symmetry Analysis ===",
            f"  File 1: {file1_name}, Channel {ch1_idx + 1} ({result.file1_sample_rate:.0f} Hz)",
            f"  File 2: {file2_name}, Channel {ch2_idx + 1} ({result.file2_sample_rate:.0f} Hz)",
            f"  Analysis sample rate: {result.analysis_sample_rate:.0f} Hz",
            f"  Overlap duration: {result.overlap_duration:.2f} s",
            f"  Window size: {result.window_duration:.3f} s",
            "",
            "--- Summary Statistics ---",
            f"  Mean Symmetry Index: {result.mean_si:+.4f}",
            f"  Std Symmetry Index:  {result.std_si:.4f}",
            f"  Max Asymmetry:       {result.max_asymmetry:.4f}",
            f"  Overall RMS File 1:  {result.rms_file1:.6f}",
            f"  Overall RMS File 2:  {result.rms_file2:.6f}",
            "",
            "--- Interpretation ---",
            "  SI near 0 = symmetric",
            "  SI > 0 = File 1 dominant",
            "  SI < 0 = File 2 dominant",
        ]

        abs_mean = abs(result.mean_si)
        if abs_mean < 0.1:
            assessment = "GOOD SYMMETRY (|mean SI| < 0.1)"
        elif abs_mean < 0.25:
            assessment = "MILD ASYMMETRY (0.1 < |mean SI| < 0.25)"
        elif abs_mean < 0.5:
            assessment = "MODERATE ASYMMETRY (0.25 < |mean SI| < 0.5)"
        else:
            assessment = "SEVERE ASYMMETRY (|mean SI| > 0.5)"

        lines.append(f"  Assessment: {assessment}")

        self.feature_results_text.setText("\n".join(lines))
        self._update_view()

    def _on_fatigue_analysis(self):
        """Compute fatigue analysis on selected channel(s) and add feature tracks."""
        if self.csv_loader is None or not self.csv_loader.is_loaded():
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        if self.track_manager is None:
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        selected = self.track_manager.get_selected_channels()
        if len(selected) == 0:
            QtWidgets.QMessageBox.warning(
                self, "No Channel Selected",
                "Please select at least one channel in the Data Viewing tab."
            )
            return

        self.track_manager.remove_feature_tracks()
        self.feature_results_text.clear()

        raw_data = self.csv_loader.data
        timestamps = self.csv_loader.timestamps
        sample_rate = self.csv_loader.sample_rate
        base_time = timestamps[0]

        self._last_feature_results = []
        self._last_feature_type = 'fatigue'
        self._last_bilateral_meta = {}

        errors = []
        results_text_parts = []
        for ch_idx in selected:
            ch_signal = raw_data[ch_idx, :]

            result = compute_fatigue(
                raw_signal=ch_signal,
                timestamps=timestamps,
                sample_rate=sample_rate,
            )

            if result is None:
                errors.append(f"Channel {ch_idx + 1}")
                continue

            self._last_feature_results.append((ch_idx, result))

            # Add RMS trend as a feature track
            rms_title = f"Fatigue RMS - Ch {ch_idx + 1}"
            self.track_manager.add_feature_track(
                title=rms_title,
                timestamps=result.rms_times,
                data_1d=result.rms_values,
                sample_rate=result.sample_rate,
            )

            # Add median frequency trend as a feature track
            mf_title = f"Fatigue MF - Ch {ch_idx + 1}"
            self.track_manager.add_feature_track(
                title=mf_title,
                timestamps=result.mf_times,
                data_1d=result.mf_values,
                sample_rate=result.sample_rate,
            )

            # Build results text
            lines = [
                f"=== Channel {ch_idx + 1}: Fatigue Analysis ===",
                f"  Baseline RMS: {result.baseline_rms:.6f}",
                f"  RMS threshold: {result.rms_threshold * 100:.1f}% increase",
                f"  MF threshold: {result.mf_threshold:.2f} Hz/sec decline",
                "",
            ]

            if result.time_to_rms_fatigue is not None and len(result.time_to_rms_fatigue) > 0:
                first_rms = result.time_to_rms_fatigue[0] - base_time
                lines.append(f"  RMS Fatigue onset: {first_rms:.2f}s")
                lines.append(f"  Total RMS fatigue detections: {len(result.time_to_rms_fatigue)}")
            else:
                lines.append("  RMS Fatigue: Not detected")

            if result.time_to_mf_fatigue is not None and len(result.time_to_mf_fatigue) > 0:
                first_mf = result.time_to_mf_fatigue[0] - base_time
                lines.append(f"  MF Fatigue onset: {first_mf:.2f}s")
                lines.append(f"  Total MF fatigue detections: {len(result.time_to_mf_fatigue)}")
            else:
                lines.append("  MF Fatigue: Not detected")

            # Determine earliest indicator
            first_rms_t = result.time_to_rms_fatigue[0] if result.time_to_rms_fatigue is not None and len(result.time_to_rms_fatigue) > 0 else None
            first_mf_t = result.time_to_mf_fatigue[0] if result.time_to_mf_fatigue is not None and len(result.time_to_mf_fatigue) > 0 else None

            if first_rms_t is not None and first_mf_t is not None:
                earliest = min(first_rms_t, first_mf_t) - base_time
                indicator = "RMS" if first_rms_t <= first_mf_t else "MF"
                lines.append(f"  Earliest indicator: {indicator} at {earliest:.2f}s")
            elif first_rms_t is not None:
                lines.append(f"  Earliest indicator: RMS at {first_rms_t - base_time:.2f}s")
            elif first_mf_t is not None:
                lines.append(f"  Earliest indicator: MF at {first_mf_t - base_time:.2f}s")
            else:
                lines.append("  No fatigue detected in this recording")

            results_text_parts.append("\n".join(lines))

        if results_text_parts:
            self.feature_results_text.setText("\n\n".join(results_text_parts))
        else:
            self.feature_results_text.setText("No fatigue detected.")

        if errors:
            QtWidgets.QMessageBox.warning(
                self, "Processing Warning",
                f"Fatigue computation failed for: {', '.join(errors)}.\n"
                "The signal may be too short or contain invalid data."
            )

        self._update_view()

    def _on_centroid_shift(self):
        """Compute HD-EMG activation centroid shift on all 64 channels and add feature tracks."""
        if self.csv_loader is None or not self.csv_loader.is_loaded():
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        if self.track_manager is None:
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        if self.csv_loader.data.shape[0] != 64:
            QtWidgets.QMessageBox.warning(
                self, "Incompatible Data",
                f"Centroid Shift requires exactly 64 channels (HD-EMG 8x8 grid).\n"
                f"This file has {self.csv_loader.data.shape[0]} channel(s)."
            )
            return

        self.track_manager.remove_feature_tracks()
        self.feature_results_text.clear()

        self._last_feature_results = []
        self._last_feature_type = 'centroid'
        self._last_bilateral_meta = {}

        result = compute_centroid_shift(
            data_64ch=self.csv_loader.data,
            timestamps=self.csv_loader.timestamps,
            sample_rate=self.csv_loader.sample_rate,
        )

        if result is None:
            QtWidgets.QMessageBox.warning(
                self, "Computation Failed",
                "Centroid shift computation failed.\n"
                "The recording may be too short or contain invalid data."
            )
            return

        self._last_feature_results = [(0, result)]

        base_time = self.csv_loader.timestamps[0]
        rel_times = result.times - base_time

        # Add three feature tracks using relative timestamps
        self.track_manager.add_feature_track(
            title="Centroid X (column)",
            timestamps=rel_times,
            data_1d=result.centroid_x,
            sample_rate=result.sample_rate,
        )
        self.track_manager.add_feature_track(
            title="Centroid Y (row)",
            timestamps=rel_times,
            data_1d=result.centroid_y,
            sample_rate=result.sample_rate,
        )
        self.track_manager.add_feature_track(
            title="Centroid Displacement (electrode-units)",
            timestamps=rel_times,
            data_1d=result.displacement,
            sample_rate=result.sample_rate,
        )

        cx0, cy0 = result.initial_centroid
        cx_final = float(result.centroid_x[-1])
        cy_final = float(result.centroid_y[-1])
        duration = float(result.times[-1] - result.times[0])

        lines = [
            "=== Centroid Shift Analysis (HD-EMG 8x8) ===",
            f"  Initial centroid:    col={cx0:.2f}, row={cy0:.2f}",
            f"  Final centroid:      col={cx_final:.2f}, row={cy_final:.2f}",
            f"  Total displacement:  {result.total_shift:.3f} electrode-units",
            f"  Mean drift rate:     {result.mean_drift_rate:.4f} electrode-units/s",
            f"  Duration analyzed:   {duration:.2f} s",
        ]
        self.feature_results_text.setText("\n".join(lines))
        self._update_view()

    def _on_spatial_nonuniformity(self):
        """Compute spatial non-uniformity and activation area on all 64 channels."""
        if self.csv_loader is None or not self.csv_loader.is_loaded():
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        if self.track_manager is None:
            QtWidgets.QMessageBox.warning(self, "No Data", "Please load a CSV file first.")
            return

        if self.csv_loader.data.shape[0] != 64:
            QtWidgets.QMessageBox.warning(
                self, "Incompatible Data",
                f"Spatial Non-Uniformity requires exactly 64 channels (HD-EMG 8x8 grid).\n"
                f"This file has {self.csv_loader.data.shape[0]} channel(s)."
            )
            return

        # Attempt to load per-channel calibration thresholds from previous session
        threshold_per_channel = None
        session_path = os.path.join(get_data_dir(), 'previous_session.csv')
        if os.path.exists(session_path):
            try:
                with open(session_path, 'r', newline='') as f:
                    row = next(csv.DictReader(f), None)
                    if row and row.get('is_calibrated', '').lower() == 'true':
                        vals = row.get('threshold_values', '')
                        if vals:
                            arr = [float(x) for x in vals.split(',') if x.strip()]
                            if len(arr) == 64:
                                threshold_per_channel = np.array(arr)
            except Exception:
                pass  # Fall through to auto-threshold

        self.track_manager.remove_feature_tracks()
        self.feature_results_text.clear()

        self._last_feature_results = []
        self._last_feature_type = 'spatial'
        self._last_bilateral_meta = {}

        result = compute_spatial_nonuniformity(
            data_64ch=self.csv_loader.data,
            timestamps=self.csv_loader.timestamps,
            sample_rate=self.csv_loader.sample_rate,
            threshold_per_channel=threshold_per_channel,
        )

        if result is None:
            QtWidgets.QMessageBox.warning(
                self, "Computation Failed",
                "Spatial non-uniformity computation failed.\n"
                "The recording may be too short or contain invalid data."
            )
            return

        self._last_feature_results = [(0, result)]

        base_time = self.csv_loader.timestamps[0]
        rel_times = result.times - base_time

        self.track_manager.add_feature_track(
            title="Spatial CV",
            timestamps=rel_times,
            data_1d=result.cv,
            sample_rate=result.sample_rate,
        )
        self.track_manager.add_feature_track(
            title="Spatial Entropy (bits)",
            timestamps=rel_times,
            data_1d=result.entropy,
            sample_rate=result.sample_rate,
        )
        self.track_manager.add_feature_track(
            title="Activation Area (fraction)",
            timestamps=rel_times,
            data_1d=result.activation_fraction,
            sample_rate=result.sample_rate,
        )

        mean_cv = float(result.cv.mean())
        mean_entropy = float(result.entropy.mean())
        mean_area = float(result.activation_fraction.mean()) * 100.0
        peak_area = float(result.activation_fraction.max()) * 100.0
        peak_idx = int(result.activation_fraction.argmax())
        peak_time = float(rel_times[peak_idx])

        lines = [
            "=== Spatial Non-Uniformity Analysis (HD-EMG 8x8) ===",
            f"  Threshold source:      {result.threshold_source}",
            f"  Mean CV:               {mean_cv:.4f}  (higher = more uneven)",
            f"  Mean entropy:          {mean_entropy:.2f} bits  (max 6.00 = fully uniform)",
            f"  Mean activation area:  {mean_area:.1f}% of 64 channels",
            f"  Peak activation area:  {peak_area:.1f}% at {peak_time:.2f}s",
        ]
        self.feature_results_text.setText("\n".join(lines))
        self._update_view()

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

    def _on_export_results(self):
        """Export processed signal and feature analysis results to CSV."""
        if self.csv_loader is None or not self.csv_loader.is_loaded():
            QtWidgets.QMessageBox.warning(self, "No Data", "Load a recording file first.")
            return

        default_name = os.path.splitext(
            os.path.basename(self.csv_loader.file_path)
        )[0] + "_export.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Analysis", default_name, "CSV files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)

                # Metadata
                ts = self.csv_loader.timestamps
                w.writerow(['# OTB-EMG Analysis Export'])
                w.writerow([f'# Source: {os.path.basename(self.csv_loader.file_path)}'])
                w.writerow([f'# Exported: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                w.writerow([f'# Channels: {self.csv_loader.data.shape[0]}'])
                w.writerow([f'# Sample rate: {self.csv_loader.sample_rate:.1f} Hz'])
                w.writerow([f'# Duration: {ts[-1] - ts[0]:.3f} s'])
                w.writerow([])

                # Processed signal for each selected channel
                selected = self.track_manager.get_selected_channels() if self.track_manager else []
                if selected:
                    dvp = self.data_viewing_panel
                    rectified = dvp.rectify_checkbox.isChecked()
                    if dvp.envelope_rms_radio.isChecked():
                        env_label = f"RMS ({dvp.rms_window_input.text()} samples)"
                    elif dvp.envelope_lowpass_radio.isChecked():
                        env_label = f"Lowpass ({dvp.lowpass_cutoff_input.text()} Hz)"
                    else:
                        env_label = "None"

                    for ch_idx in selected:
                        ch_name = self.csv_loader.channel_names[ch_idx]
                        processed = self.track_manager.track.data[ch_idx, :]
                        w.writerow([f'## PROCESSED SIGNAL ({ch_name})'])
                        w.writerow([f'# Rectified: {rectified}'])
                        w.writerow([f'# Envelope: {env_label}'])
                        w.writerow(['time_s', 'emg_value'])
                        for t, v in zip(ts, processed):
                            w.writerow([round(float(t), 6), round(float(v), 8)])
                        w.writerow([])

                # Feature results
                if self._last_feature_results:
                    self._write_feature_csv(w)
                else:
                    w.writerow(['## No feature analysis has been run'])

            QtWidgets.QMessageBox.information(self, "Export Complete", f"Saved to:\n{path}")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", f"Export failed: {e}")

    def _write_feature_csv(self, w):
        """Write feature analysis results to the CSV writer."""
        base_time = self.csv_loader.timestamps[0]

        if self._last_feature_type == 'tkeo':
            for ch_idx, result in self._last_feature_results:
                w.writerow([f'## ACTIVATION TIMINGS (Channel {ch_idx + 1})'])
                w.writerow([f'# Onsets detected: {len(result.onset_times)}'])
                w.writerow([f'# Detection threshold: {result.detection_threshold:.8f}'])
                w.writerow([f'# Backtrack threshold: {result.backtrack_threshold:.8f}'])
                w.writerow(['onset_number', 'onset_time_s'])
                for i, t in enumerate(result.onset_times):
                    w.writerow([i + 1, round(float(t) - base_time, 6)])
                w.writerow([])
                w.writerow([f'## TKEO ENVELOPE (Channel {ch_idx + 1})'])
                w.writerow(['time_s', 'tkeo_envelope'])
                env_base = result.timestamps[0]
                for t, v in zip(result.timestamps, result.tkeo_envelope):
                    w.writerow([round(float(t) - env_base, 6), round(float(v), 10)])
                w.writerow([])

        elif self._last_feature_type == 'burst':
            for ch_idx, result in self._last_feature_results:
                w.writerow([f'## BURST DURATION (Channel {ch_idx + 1})'])
                w.writerow([f'# Number of bursts: {result.num_bursts}'])
                w.writerow([f'# Average duration: {result.avg_duration:.4f} s'])
                w.writerow([f'# Std duration: {result.std_duration:.4f} s'])
                w.writerow(['burst_number', 'duration_s'])
                for i, d in enumerate(result.burst_durations):
                    w.writerow([i + 1, round(float(d), 6)])
                w.writerow([])

        elif self._last_feature_type == 'bilateral':
            meta = self._last_bilateral_meta
            ch1_idx, result = self._last_feature_results[0]
            w.writerow(['## BILATERAL SYMMETRY'])
            w.writerow([f'# File 1: {meta.get("file1", "")}, Channel {meta.get("ch1_idx", 0) + 1}'])
            w.writerow([f'# File 2: {meta.get("file2", "")}, Channel {meta.get("ch2_idx", 0) + 1}'])
            w.writerow([f'# Overlap duration: {result.overlap_duration:.3f} s'])
            w.writerow([f'# Window size: {result.window_duration:.3f} s'])
            w.writerow([f'# Mean SI: {result.mean_si:+.6f}'])
            w.writerow([f'# Std SI: {result.std_si:.6f}'])
            w.writerow([f'# Max asymmetry: {result.max_asymmetry:.6f}'])
            w.writerow([f'# Overall RMS File 1: {result.rms_file1:.8f}'])
            w.writerow([f'# Overall RMS File 2: {result.rms_file2:.8f}'])
            w.writerow(['time_s', 'symmetry_index'])
            si_base = result.timestamps[0]
            for t, v in zip(result.timestamps, result.symmetry_index):
                w.writerow([round(float(t) - si_base, 6), round(float(v), 8)])
            w.writerow([])

        elif self._last_feature_type == 'fatigue':
            for ch_idx, result in self._last_feature_results:
                w.writerow([f'## FATIGUE ANALYSIS (Channel {ch_idx + 1})'])
                w.writerow([f'# Baseline RMS: {result.baseline_rms:.8f}'])
                if result.time_to_rms_fatigue is not None and len(result.time_to_rms_fatigue) > 0:
                    w.writerow([f'# RMS fatigue onset: {result.time_to_rms_fatigue[0] - base_time:.3f} s'])
                else:
                    w.writerow(['# RMS fatigue onset: Not detected'])
                if result.time_to_mf_fatigue is not None and len(result.time_to_mf_fatigue) > 0:
                    w.writerow([f'# MF fatigue onset: {result.time_to_mf_fatigue[0] - base_time:.3f} s'])
                else:
                    w.writerow(['# MF fatigue onset: Not detected'])
                w.writerow(['time_s', 'rms_value', 'median_freq_hz'])
                for t, r, m in zip(result.rms_times, result.rms_values, result.mf_values):
                    w.writerow([round(float(t) - base_time, 6),
                                round(float(r), 8),
                                round(float(m), 4)])
                w.writerow([])

        elif self._last_feature_type == 'spatial':
            _, result = self._last_feature_results[0]
            w.writerow(['## SPATIAL NON-UNIFORMITY (HD-EMG 8x8)'])
            w.writerow([f'# Threshold source: {result.threshold_source}'])
            w.writerow([f'# Mean CV: {float(result.cv.mean()):.6f}'])
            w.writerow([f'# Mean entropy (bits): {float(result.entropy.mean()):.6f}'])
            w.writerow([f'# Mean activation fraction: {float(result.activation_fraction.mean()):.6f}'])
            w.writerow(['time_s', 'cv', 'entropy_bits', 'activation_fraction'])
            for t, c, e, a in zip(result.times, result.cv, result.entropy, result.activation_fraction):
                w.writerow([round(float(t) - base_time, 6),
                            round(float(c), 6),
                            round(float(e), 6),
                            round(float(a), 6)])
            w.writerow([])

        elif self._last_feature_type == 'centroid':
            _, result = self._last_feature_results[0]
            cx0, cy0 = result.initial_centroid
            w.writerow(['## CENTROID SHIFT ANALYSIS (HD-EMG 8x8)'])
            w.writerow([f'# Initial centroid: col={cx0:.4f}, row={cy0:.4f}'])
            w.writerow([f'# Total displacement: {result.total_shift:.6f} electrode-units'])
            w.writerow([f'# Mean drift rate: {result.mean_drift_rate:.6f} electrode-units/s'])
            w.writerow(['time_s', 'centroid_col', 'centroid_row', 'displacement_electrode_units'])
            for t, cx, cy, d in zip(result.times, result.centroid_x, result.centroid_y, result.displacement):
                w.writerow([round(float(t) - base_time, 6),
                            round(float(cx), 6),
                            round(float(cy), 6),
                            round(float(d), 6)])
            w.writerow([])

    def closeEvent(self, event):
        """Handle window close event."""
        event.accept()
