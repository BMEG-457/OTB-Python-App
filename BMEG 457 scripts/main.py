from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

from app.core.device import SessantaquattroPlus
from app.ui.windows.main_window import SoundtrackWindow
# control window not used; using built-in controls in SoundtrackWindow


class SelectionWindow(QtWidgets.QWidget):
    """Initial selection window with mode choices."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OTB-Python-App - Mode Selection")
        self.setGeometry(300, 300, 400, 300)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title = QtWidgets.QLabel("Select Mode")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin: 20px;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)
        
        # Buttons
        self.live_data_button = QtWidgets.QPushButton("Live Data Viewing")
        self.live_data_button.setMinimumHeight(60)
        self.live_data_button.setStyleSheet("font-size: 16px;")
        
        self.data_analysis_button = QtWidgets.QPushButton("Data Analysis")
        self.data_analysis_button.setMinimumHeight(60)
        self.data_analysis_button.setStyleSheet("font-size: 16px;")
        
        layout.addWidget(self.live_data_button)
        layout.addWidget(self.data_analysis_button)
        layout.addStretch()


class DataAnalysisWindow(QtWidgets.QWidget):
    """Placeholder window for data analysis mode."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Analysis")
        self.setGeometry(100, 100, 800, 600)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Back button in top left
        back_layout = QtWidgets.QHBoxLayout()
        self.back_button = QtWidgets.QPushButton("← Back")
        self.back_button.setMaximumWidth(100)
        back_layout.addWidget(self.back_button)
        back_layout.addStretch()
        layout.addLayout(back_layout)
        
        # Placeholder content
        label = QtWidgets.QLabel("Data Analysis Mode\n\n(To be implemented)")
        label.setStyleSheet("font-size: 18px;")
        label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(label)


def main():
    app = QtWidgets.QApplication([])
    pg.setConfigOptions(antialias=True)

    # Create device object, but DO NOT connect yet
    device = SessantaquattroPlus()

    # Create windows
    selection_window = SelectionWindow()
    data_analysis_window = DataAnalysisWindow()
    live_data_window = SoundtrackWindow(device)  # Renamed for clarity
    
    # Show selection window first
    selection_window.show()

    # Toggle streaming handler
    def handle_stream_toggle():
        try:
            # Check if we need to initialize the device connection first
            if live_data_window.receiver_thread is None:
                print("=" * 60)
                print("Sessantaquattro+ Python Receiver")
                print("=" * 60)
                
                # Create command
                command = device.create_command(FSAMP=2, NCH=3, MODE=0,
                                               HRES=0, HPF=1, EXTEN=0,
                                               TRIG=0, REC=0, GO=1)
                
                print("\nStarting TCP server...")
                device.start_server()   # <-- Connect here
                
                print("\nSending start command...")
                device.send_command(command)
                
                print("\nInitializing visualization...")
                print("=" * 60)
                
                live_data_window.set_client_socket(device.client_socket)
                live_data_window.initialize_receiver()

            # Toggle streaming state
            live_data_window.toggle_streaming()

        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Connection Error", str(e))
    
    # Toggle recording handler
    def handle_record_toggle():
        try:
            # Check if we need to initialize the device connection first
            if live_data_window.receiver_thread is None:
                print("=" * 60)
                print("Sessantaquattro+ Python Receiver")
                print("=" * 60)
                
                # Create command
                command = device.create_command(FSAMP=2, NCH=3, MODE=0,
                                               HRES=0, HPF=1, EXTEN=0,
                                               TRIG=0, REC=0, GO=1)
                
                print("\nStarting TCP server...")
                device.start_server()   # <-- Connect here
                
                print("\nSending start command...")
                device.send_command(command)
                
                print("\nInitializing visualization...")
                print("=" * 60)
                
                live_data_window.set_client_socket(device.client_socket)
                live_data_window.initialize_receiver()

            # Toggle recording state
            live_data_window.toggle_recording()

        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Connection Error", str(e))
    
    # Calibration handler
    def handle_calibration():
        try:
            # Check if we need to initialize the device connection first
            if live_data_window.receiver_thread is None:
                print("=" * 60)
                print("Sessantaquattro+ Python Receiver")
                print("=" * 60)
                
                # Create command
                command = device.create_command(FSAMP=2, NCH=3, MODE=0,
                                               HRES=0, HPF=1, EXTEN=0,
                                               TRIG=0, REC=0, GO=1)
                
                print("\nStarting TCP server...")
                device.start_server()   # <-- Connect here
                
                print("\nSending start command...")
                device.send_command(command)
                
                print("\nInitializing visualization...")
                print("=" * 60)
                
                live_data_window.set_client_socket(device.client_socket)
                live_data_window.initialize_receiver()

            # Open calibration dialog
            live_data_window.open_calibration_dialog()

        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Connection Error", str(e))

    # Wire the live data window buttons
    live_data_window.calibrate_button.clicked.connect(handle_calibration)
    live_data_window.stream_button.clicked.connect(handle_stream_toggle)
    live_data_window.record_button.clicked.connect(handle_record_toggle)
    
    # Navigation handlers
    def show_live_data():
        selection_window.hide()
        live_data_window.show()
    
    def show_data_analysis():
        selection_window.hide()
        data_analysis_window.show()
    
    def back_to_selection_from_live():
        # Stop streaming if active
        if live_data_window.streaming_controller and live_data_window.streaming_controller.is_streaming:
            live_data_window.streaming_controller.stop_streaming()
        # Stop recording if active
        if live_data_window.recording_manager.is_recording:
            live_data_window.stop_recording()
        live_data_window.hide()
        selection_window.show()
    
    def back_to_selection_from_analysis():
        data_analysis_window.hide()
        selection_window.show()
    
    # Wire selection window buttons
    selection_window.live_data_button.clicked.connect(show_live_data)
    selection_window.data_analysis_button.clicked.connect(show_data_analysis)
    
    # Wire back buttons
    live_data_window.back_button.clicked.connect(back_to_selection_from_live)
    data_analysis_window.back_button.clicked.connect(back_to_selection_from_analysis)

    import sys
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
