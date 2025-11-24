from PyQt5 import QtWidgets, QtCore

# button for starting/stopping recording
class ControlWindow(QtWidgets.QWidget):
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
