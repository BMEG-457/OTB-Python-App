from PyQt5 import QtWidgets
import pyqtgraph as pg

from app.device import SessantaquattroPlus
from app.window import SoundtrackWindow
# control window not used; using built-in controls in SoundtrackWindow


def main():
    app = QtWidgets.QApplication([])
    pg.setConfigOptions(antialias=True)

    # Create device object, but DO NOT connect yet
    device = SessantaquattroPlus()

    # Visualization window (not yet initialized with a socket)
    window = SoundtrackWindow(device)
    window.show()

    # Toggle streaming handler
    def handle_stream_toggle():
        try:
            # Check if we need to initialize the device connection first
            if window.receiver_thread is None:
                device.create_command(FSAMP=0, NCH=0, MODE=0,
                                        HRES=0, HPF=0, EXTEN=0,
                                        TRIG=0, REC=0, GO=0)
                device.start_server()   # <-- Connect here
                window.set_client_socket(device.client_socket)
                window.initialize_receiver()

            # Toggle streaming state
            if not window.is_streaming:
                window.start_streaming()
            else:
                window.stop_streaming()

        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Connection Error", str(e))
    
    # Toggle recording handler
    def handle_record_toggle():
        try:
            # Check if we need to initialize the device connection first
            if window.receiver_thread is None:
                device.create_command(FSAMP=0, NCH=0, MODE=0,
                                        HRES=0, HPF=0, EXTEN=0,
                                        TRIG=0, REC=0, GO=0)
                device.start_server()   # <-- Connect here
                window.set_client_socket(device.client_socket)
                window.initialize_receiver()

            # Toggle recording state
            if not window.is_recording:
                window.start_recording()
            else:
                window.stop_recording()

        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Connection Error", str(e))

    # Wire the buttons
    window.stream_button.clicked.connect(handle_stream_toggle)
    window.record_button.clicked.connect(handle_record_toggle)

    app.exec_()

if __name__ == "__main__":
    main()
