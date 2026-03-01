"""Features control panel for the data analysis window."""

from PyQt5 import QtWidgets


class FeaturesPanel(QtWidgets.QWidget):
    """Control panel for feature analysis: activation timings, burst duration, bilateral symmetry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Create all control widgets."""
        layout = QtWidgets.QVBoxLayout(self)

        self.activation_timings_button = QtWidgets.QPushButton("Activation Timings")
        layout.addWidget(self.activation_timings_button)

        self.burst_duration_button = QtWidgets.QPushButton("Burst Duration")
        layout.addWidget(self.burst_duration_button)

        self.bilateral_symmetry_button = QtWidgets.QPushButton("Bilateral Symmetry")
        layout.addWidget(self.bilateral_symmetry_button)

        self.fatigue_analysis_button = QtWidgets.QPushButton("Fatigue Analysis")
        layout.addWidget(self.fatigue_analysis_button)

        self.centroid_shift_button = QtWidgets.QPushButton("Centroid Shift")
        layout.addWidget(self.centroid_shift_button)

        self.spatial_nonuniformity_button = QtWidgets.QPushButton("Spatial Non-Uniformity")
        layout.addWidget(self.spatial_nonuniformity_button)

        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(separator)

        self.export_button = QtWidgets.QPushButton("Export Results")
        layout.addWidget(self.export_button)

        layout.addStretch()
