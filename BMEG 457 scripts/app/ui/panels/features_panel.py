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

        layout.addStretch()
