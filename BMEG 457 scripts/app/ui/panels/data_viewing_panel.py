"""Data viewing control panel for the data analysis window."""

from PyQt5 import QtWidgets, QtGui


class DataViewingPanel(QtWidgets.QWidget):
    """Control panel for data viewing settings: channel selection and signal processing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Create all control widgets."""
        ctrl_layout = QtWidgets.QVBoxLayout(self)

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
