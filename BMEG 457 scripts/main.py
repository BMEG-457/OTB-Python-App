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

    # Start/Stop handlers will be wired to the window's buttons
    def handle_start():
        try:
            device.create_command(FSAMP=0, NCH=0, MODE=0,
                                    HRES=0, HPF=0, EXTEN=0,
                                    TRIG=0, REC=0, GO=0)

            device.start_server()   # <-- Connect here

            window.set_client_socket(device.client_socket)
            window.initialize_receiver()

            window.start_recording()
            # toggle buttons
            try:
                window.start_button.setEnabled(False)
                window.stop_button.setEnabled(True)
            except Exception:
                pass

        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Connection Error", str(e))

    def handle_stop():
        try:
            window.stop_recording()
            window.start_button.setEnabled(True)
            window.stop_button.setEnabled(False)
        except Exception:
            pass

    # wire the window's buttons
    window.start_button.clicked.connect(handle_start)
    window.stop_button.clicked.connect(handle_stop)

    app.exec_()

if __name__ == "__main__":
    main()
