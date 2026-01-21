"""Legacy control window - not currently integrated into main application.

This module contains a simple control window with start/stop buttons.
Kept for potential future use or reference. The main application now uses
integrated controls in SoundtrackWindow (main_window.py).
"""

from PyQt5 import QtWidgets, QtCore


class ControlWindow(QtWidgets.QWidget):
    """Legacy control window with start/stop recording buttons.

    Note: This class is not currently used in the main application flow.
    Recording controls are now integrated directly into SoundtrackWindow.
    """
    start_clicked = QtCore.pyqtSignal()
    stop_clicked = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Sessantaquattro+ Controls")
        self.setFixedSize(500, 240)

        layout = QtWidgets.QVBoxLayout()

        self.start_button = QtWidgets.QPushButton("Start Recording")
        self.stop_button = QtWidgets.QPushButton("Stop Recording")
        self.stop_button.setEnabled(False)

        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        self.setLayout(layout)

        self.start_button.clicked.connect(self.start_clicked.emit)
        self.stop_button.clicked.connect(self.stop_clicked.emit)
