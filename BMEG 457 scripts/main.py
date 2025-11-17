from PyQt5 import QtWidgets
import pyqtgraph as pg

from app.device import SessantaquattroPlus
from app.window import SoundtrackWindow
from app.ui.control_window import ControlWindow


def main():
    app = QtWidgets.QApplication([])
    pg.setConfigOptions(antialias=True)

    # Create device object, but DO NOT connect yet
    device = SessantaquattroPlus()

    # Visualization window (not yet initialized with a socket)
    window = SoundtrackWindow(device)
    window.hide()

    # Control UI
    ctrl = ControlWindow()
    ctrl.show()

    # Start button: connect → create command → start server → show window → begin recording
    def handle_start():
        try:
            device.create_command(FSAMP=0, NCH=0, MODE=0,
                                  HRES=0, HPF=0, EXTEN=0,
                                  TRIG=0, REC=0, GO=0)

            device.start_server()   # <-- Connect here

            window.set_client_socket(device.client_socket)
            window.initialize_receiver()

            window.start_recording()
            window.show()

        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Connection Error", str(e))

    ctrl.start_clicked.connect(handle_start)
    ctrl.stop_clicked.connect(window.stop_recording)

    app.exec_()


if __name__ == "__main__":
    main()
