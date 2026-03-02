"""Live data viewing screen."""

import threading
import numpy as np

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock

from app.data.data_receiver import DataReceiverThread
from app.managers.recording_manager import RecordingManager
from app.managers.streaming_controller import StreamingController
from app.processing.pipeline import get_pipeline
from app.processing import filters
from app.ui.widgets.emg_plot_widget import EMGPlotWidget
from app.ui.widgets.calibration_popup import CalibrationPopup
from app.core import config as CFG


class LiveDataScreen(Screen):
    """Main live-streaming screen.

    Equivalent to the desktop's SoundtrackWindow. Contains:
    - Top bar: Back, Calibrate, Stream, Record buttons + status label
    - Real-time EMG plot (channel 0)
    - Status label at the bottom
    """

    def __init__(self, device, **kwargs):
        super().__init__(**kwargs)
        self.device = device

        # App state
        self.receiver_thread = None
        self.streaming_controller = None
        self.recording_manager = RecordingManager(
            on_overflow=self._on_recording_overflow,
            on_status=self._on_status_update,
        )
        self.is_calibrated = False
        self.baseline_rms = None
        self.threshold = None
        self.mvc_rms = None

        # Extra callbacks registered during calibration
        self._calibration_extra_callback = None

        self._build_ui()
        self._configure_pipelines()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = BoxLayout(orientation='vertical')

        # Top bar
        top_bar = BoxLayout(orientation='horizontal', size_hint=(1, 0.1), padding=4, spacing=4)

        btn_back = Button(text='Back', size_hint=(0.1, 1))
        btn_back.bind(on_press=self._go_back)
        top_bar.add_widget(btn_back)

        self.btn_calibrate = Button(text='Calibrate', size_hint=(0.15, 1))
        self.btn_calibrate.bind(on_press=self._on_calibrate)
        self.btn_calibrate.disabled = True  # needs stream first
        top_bar.add_widget(self.btn_calibrate)

        self.btn_stream = Button(text='Start Stream', size_hint=(0.15, 1),
                                 background_color=(0.1, 0.6, 0.3, 1))
        self.btn_stream.bind(on_press=self._on_toggle_stream)
        top_bar.add_widget(self.btn_stream)

        self.btn_record = Button(text='Start Record', size_hint=(0.15, 1),
                                 background_color=(0.6, 0.1, 0.1, 1))
        self.btn_record.bind(on_press=self._on_toggle_record)
        self.btn_record.disabled = True  # needs calibration
        top_bar.add_widget(self.btn_record)

        self.contraction_label = Label(
            text='No Contraction',
            color=(0.8, 0.3, 0.3, 1),
            size_hint=(0.2, 1),
            font_size=14,
        )
        top_bar.add_widget(self.contraction_label)

        # Status label (right side of bar)
        self.status_label = Label(
            text='Not connected',
            color=(0.7, 0.7, 0.7, 1),
            size_hint=(0.25, 1),
            font_size=12,
        )
        top_bar.add_widget(self.status_label)

        root.add_widget(top_bar)

        # Plot area
        self.plot_widget = EMGPlotWidget(channel_index=0, size_hint=(1, 0.85))
        root.add_widget(self.plot_widget)

        # Bottom status bar
        self.bottom_label = Label(
            text='Press "Start Stream" to connect to the device.',
            font_size=12,
            color=(0.6, 0.6, 0.6, 1),
            size_hint=(1, 0.05),
        )
        root.add_widget(self.bottom_label)

        self.add_widget(root)

    def _configure_pipelines(self):
        """Set up the three processing pipelines (filtered, rectified, final)."""
        get_pipeline('filtered').add_stage(filters.butter_bandpass)
        get_pipeline('rectified').add_stage(filters.rectify)
        get_pipeline('final').add_stage(filters.butter_bandpass)
        get_pipeline('final').add_stage(filters.notch)
        get_pipeline('final').add_stage(filters.rectify)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_back(self, instance):
        if self.streaming_controller and self.streaming_controller.is_streaming:
            self.streaming_controller.stop_streaming()
        self.manager.current = 'selection'

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def _on_toggle_stream(self, instance):
        if self.streaming_controller and self.streaming_controller.is_streaming:
            self._stop_stream()
        else:
            self._start_stream()

    def _start_stream(self):
        """Connect to device in background then start receiver."""
        self.btn_stream.disabled = True
        self.btn_stream.text = 'Connecting...'
        self._set_status('Waiting for device...')

        def connect():
            try:
                self.device.start_server(connection_timeout=CFG.DEVICE_CONNECT_TIMEOUT)
                command = self.device.create_command(
                    FSAMP=CFG.DEVICE_FSAMP, NCH=CFG.DEVICE_NCH,
                    MODE=CFG.DEVICE_MODE,   HPF=CFG.DEVICE_HPF, GO=1,
                )
                self.device.send_command(command)
                Clock.schedule_once(self._on_connected, 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self._on_connect_error(str(e)), 0)

        threading.Thread(target=connect, daemon=True).start()

    def _on_connected(self, dt):
        """Called on the UI thread once the device has connected."""
        self.receiver_thread = DataReceiverThread(
            device=self.device,
            client_socket=self.device.client_socket,
            on_stage=self._on_data,
            on_error=lambda msg: Clock.schedule_once(lambda dt: self._on_receiver_error(msg), 0),
            on_status=lambda msg: Clock.schedule_once(lambda dt: self._set_status(msg), 0),
        )

        self.streaming_controller = StreamingController(
            update_callback=self._ui_tick,
            receiver_thread=self.receiver_thread,
            on_status=self._set_status,
        )

        self.streaming_controller.start_streaming()
        self.btn_stream.text = 'Stop Stream'
        self.btn_stream.disabled = False
        self.btn_calibrate.disabled = False
        self._set_status('Streaming...')
        self._set_bottom('Connected — receiving data.')

    def _on_connect_error(self, message):
        self.btn_stream.text = 'Start Stream'
        self.btn_stream.disabled = False
        self._set_status('Connection failed')
        self._set_bottom(f'Error: {message}')

    def _stop_stream(self):
        if self.streaming_controller:
            self.streaming_controller.stop_streaming()
        self.btn_stream.text = 'Start Stream'
        self.btn_calibrate.disabled = True
        self.btn_record.disabled = True
        self._set_status('Stream stopped')

    def _on_receiver_error(self, message):
        self._set_bottom(f'Receiver error: {message}')
        self._stop_stream()

    # ------------------------------------------------------------------
    # Data callback (background thread → UI thread via Clock)
    # ------------------------------------------------------------------

    def _on_data(self, stage, data):
        """Called by receiver thread for every processed packet."""
        # Recording: forward raw data on the receiver thread directly
        self.recording_manager.on_data_for_recording(stage, data)

        # Calibration extra listener (if active)
        if self._calibration_extra_callback is not None:
            self._calibration_extra_callback(stage, data)

        # UI update must happen on the main thread
        if stage == 'final':
            data_copy = data.copy()
            Clock.schedule_once(lambda dt: self.plot_widget.update(data_copy), 0)

            # Contraction detection (simple threshold on channel 0 mean RMS)
            if self.is_calibrated and self.threshold is not None:
                ch0_rms = float(np.sqrt(np.mean(data[0] ** 2)))
                label = 'Contraction' if ch0_rms > self.threshold[0] else 'No Contraction'
                color = (0.2, 0.9, 0.4, 1) if ch0_rms > self.threshold[0] else (0.8, 0.3, 0.3, 1)
                Clock.schedule_once(lambda dt, lbl=label, clr=color: self._update_contraction(lbl, clr), 0)

    def _ui_tick(self, dt):
        """Called by Kivy Clock at ~60fps. Plot updates happen in _on_data."""
        pass

    def _update_contraction(self, text, color):
        self.contraction_label.text = text
        self.contraction_label.color = color

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def _on_calibrate(self, instance):
        if not (self.streaming_controller and self.streaming_controller.is_streaming):
            self._set_bottom('Start streaming before calibrating.')
            return

        popup = CalibrationPopup(
            on_complete=self._on_calibration_complete,
            on_sample_connect=self._register_calibration_callback,
            on_sample_disconnect=self._unregister_calibration_callback,
        )
        popup.start()

    def _register_calibration_callback(self, cb):
        self._calibration_extra_callback = cb

    def _unregister_calibration_callback(self, cb):
        self._calibration_extra_callback = None

    def _on_calibration_complete(self, baseline_rms, threshold, mvc_rms):
        self.baseline_rms = baseline_rms
        self.threshold = threshold
        self.mvc_rms = mvc_rms
        self.is_calibrated = True
        self.btn_record.disabled = False
        self._set_bottom('Calibration complete.')
        self._set_status('Calibrated')

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def _on_toggle_record(self, instance):
        if self.recording_manager.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self.recording_manager.start_recording()
        self.btn_record.text = 'Stop Record'
        self.btn_record.background_color = (0.8, 0.4, 0.0, 1)
        self._set_status('Recording...')

    def _stop_recording(self):
        self.recording_manager.stop_recording()
        self.btn_record.text = 'Saving...'
        self.btn_record.disabled = True

        def save():
            success, message, filename = self.recording_manager.save_recording_to_csv()
            Clock.schedule_once(lambda dt: self._on_save_done(success, message), 0)

        threading.Thread(target=save, daemon=True).start()

    def _on_save_done(self, success, message):
        self.btn_record.text = 'Start Record'
        self.btn_record.background_color = (0.6, 0.1, 0.1, 1)
        self.btn_record.disabled = False
        self._set_status('Saved' if success else 'Save failed')
        self._set_bottom(message)

    def _on_recording_overflow(self):
        Clock.schedule_once(lambda dt: self._stop_recording(), 0)
        Clock.schedule_once(lambda dt: self._set_bottom('Recording stopped: max samples reached.'), 0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, text):
        self.status_label.text = text

    def _set_bottom(self, text):
        self.bottom_label.text = text

    def _on_status_update(self, text):
        Clock.schedule_once(lambda dt: self._set_status(text), 0)
