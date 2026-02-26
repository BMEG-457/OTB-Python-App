"""Live data viewing screen."""

import threading
import numpy as np

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.metrics import sp

from app.data.data_receiver import DataReceiverThread
from app.managers.recording_manager import RecordingManager
from app.managers.streaming_controller import StreamingController
from app.processing.pipeline import get_pipeline
from app.processing import filters
from app.ui.widgets.emg_plot_widget import EMGPlotWidget
from app.ui.widgets.multi_track_plot import MultiTrackPlotWidget
from app.ui.widgets.heatmap_widget import HeatmapWidget
from app.ui.widgets.calibration_popup import CalibrationPopup
from app.core import config as CFG


# ---------------------------------------------------------------------------
# HD-EMG aggregation helpers
# channel_idx = col * 8 + (7 - row) — columns 0-7, rows 0-7, bottom-left = ch0
# Channels 0-63 = HD-EMG array; 64-71 = AUX (excluded from spatial views)
# ---------------------------------------------------------------------------

def _row_aggregates(data):
    """Mean across columns for each row. data (≥64, S) → (8, S)."""
    result = []
    for row in range(8):
        ch_indices = [col * 8 + (7 - row) for col in range(8)]
        result.append(data[ch_indices].mean(axis=0))
    return np.array(result)


def _col_aggregates(data):
    """Mean across rows for each column. data (≥64, S) → (8, S)."""
    result = []
    for col in range(8):
        ch_indices = [col * 8 + r for r in range(8)]
        result.append(data[ch_indices].mean(axis=0))
    return np.array(result)


def _cluster_aggregates(data):
    """Mean of 2x2 electrode clusters. data (≥64, S) → (16, S), 4x4 arrangement."""
    result = []
    for cr in range(4):       # cluster row
        for cc in range(4):   # cluster col
            ch_indices = []
            for dr in range(2):
                for dc in range(2):
                    row = cr * 2 + dr
                    col = cc * 2 + dc
                    ch_indices.append(col * 8 + (7 - row))
            result.append(data[ch_indices].mean(axis=0))
    return np.array(result)


# View mode definitions: (label, num_tracks, aggregation_fn or None)
_VIEW_MODES = [
    ('Single Ch0', 1,  None),
    ('Rows (8)',   8,  _row_aggregates),
    ('Cols (8)',   8,  _col_aggregates),
    ('Clusters',   16, _cluster_aggregates),
]


class LiveDataScreen(Screen):
    """Main live-streaming screen.

    Layout:
        Top bar     [0.10] — Back, Calibrate, Stream, Record, Contraction, Status
        Tab+View bar[0.07] — EMG Plot | Heatmap tabs; View mode cycle button
        Content     [0.78] — active plot panel OR heatmap panel
        Bottom bar  [0.05] — status / instructions
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

        self._calibration_extra_callback = None

        # Latest raw (72-ch) data arriving from receiver — read in _ui_tick
        self._pending_data = None

        # Per-channel rolling buffers for heatmap RMS computation (last 100 samples)
        self._heatmap_buffer = np.zeros((64, 100))
        self._heatmap_buf_idx = 0

        # View mode index into _VIEW_MODES
        self._view_mode_idx = 0

        self._build_ui()
        self._configure_pipelines()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = BoxLayout(orientation='vertical')

        # ---- Top bar ----
        top_bar = BoxLayout(
            orientation='horizontal', size_hint=(1, 0.10), padding=4, spacing=4
        )

        btn_back = Button(text='Back', size_hint=(0.08, 1), font_size=sp(15))
        btn_back.bind(on_press=self._go_back)
        top_bar.add_widget(btn_back)

        self.btn_calibrate = Button(
            text='Calibrate', size_hint=(0.13, 1), font_size=sp(15)
        )
        self.btn_calibrate.bind(on_press=self._on_calibrate)
        self.btn_calibrate.disabled = True
        top_bar.add_widget(self.btn_calibrate)

        self.btn_stream = Button(
            text='Start Stream', size_hint=(0.15, 1),
            font_size=sp(15), background_color=(0.1, 0.6, 0.3, 1)
        )
        self.btn_stream.bind(on_press=self._on_toggle_stream)
        top_bar.add_widget(self.btn_stream)

        self.btn_record = Button(
            text='Start Record', size_hint=(0.15, 1),
            font_size=sp(15), background_color=(0.6, 0.1, 0.1, 1)
        )
        self.btn_record.bind(on_press=self._on_toggle_record)
        self.btn_record.disabled = True
        top_bar.add_widget(self.btn_record)

        self.contraction_label = Label(
            text='No Contraction', color=(0.8, 0.3, 0.3, 1),
            size_hint=(0.22, 1), font_size=sp(15),
        )
        top_bar.add_widget(self.contraction_label)

        self.status_label = Label(
            text='Not connected', color=(0.7, 0.7, 0.7, 1),
            size_hint=(0.27, 1), font_size=sp(14),
        )
        top_bar.add_widget(self.status_label)

        root.add_widget(top_bar)

        # ---- Tab + View mode bar ----
        tab_bar = BoxLayout(
            orientation='horizontal', size_hint=(1, 0.07), padding=2, spacing=4
        )

        self.btn_tab_plot = ToggleButton(
            text='EMG Plot', group='tab', state='down',
            size_hint=(0.22, 1), font_size=sp(15),
        )
        self.btn_tab_plot.bind(on_press=self._on_tab_plot)
        tab_bar.add_widget(self.btn_tab_plot)

        self.btn_tab_heatmap = ToggleButton(
            text='Heatmap', group='tab', state='normal',
            size_hint=(0.22, 1), font_size=sp(15),
        )
        self.btn_tab_heatmap.bind(on_press=self._on_tab_heatmap)
        tab_bar.add_widget(self.btn_tab_heatmap)

        # Spacer
        tab_bar.add_widget(Label(size_hint=(0.22, 1)))

        self.btn_view_mode = Button(
            text=f'View: {_VIEW_MODES[0][0]}', size_hint=(0.34, 1), font_size=sp(14),
        )
        self.btn_view_mode.bind(on_press=self._on_cycle_view)
        tab_bar.add_widget(self.btn_view_mode)

        root.add_widget(tab_bar)

        # ---- Content area (FloatLayout to overlay panels) ----
        self._content = FloatLayout(size_hint=(1, 0.78))

        # Single-channel plot (default view)
        self.plot_single = EMGPlotWidget(
            channel_index=0, size_hint=(1, 1), pos_hint={'x': 0, 'y': 0}
        )

        # Multi-track plot — starts with row labels; rebuilt on mode switch
        row_labels  = [f'Row {i}' for i in range(8)]
        self.plot_multi = MultiTrackPlotWidget(
            track_labels=row_labels,
            size_hint=(1, 1), pos_hint={'x': 0, 'y': 0},
        )
        self.plot_multi.opacity = 0

        # Heatmap
        self.heatmap = HeatmapWidget(
            size_hint=(1, 1), pos_hint={'x': 0, 'y': 0}
        )
        self.heatmap.opacity = 0

        self._content.add_widget(self.plot_single)
        self._content.add_widget(self.plot_multi)
        self._content.add_widget(self.heatmap)

        root.add_widget(self._content)

        # ---- Bottom status bar ----
        self.bottom_label = Label(
            text='Press "Start Stream" to connect to the device.',
            font_size=sp(14), color=(0.6, 0.6, 0.6, 1),
            size_hint=(1, 0.05),
        )
        root.add_widget(self.bottom_label)

        self.add_widget(root)

        # Active tab state ('plot' | 'heatmap')
        self._active_tab = 'plot'

    def _configure_pipelines(self):
        get_pipeline('filtered').add_stage(filters.butter_bandpass)
        get_pipeline('rectified').add_stage(filters.rectify)
        get_pipeline('final').add_stage(filters.butter_bandpass)
        get_pipeline('final').add_stage(filters.notch)
        get_pipeline('final').add_stage(filters.rectify)

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------

    def _on_tab_plot(self, instance):
        self._active_tab = 'plot'
        self.btn_view_mode.opacity = 1
        self.btn_view_mode.disabled = False
        # Show active plot, hide heatmap
        self._show_active_plot_widget()
        self.heatmap.opacity = 0

    def _on_tab_heatmap(self, instance):
        self._active_tab = 'heatmap'
        self.btn_view_mode.opacity = 0
        self.btn_view_mode.disabled = True
        # Hide plot widgets, show heatmap
        self.plot_single.opacity = 0
        self.plot_multi.opacity = 0
        self.heatmap.opacity = 1

    def _show_active_plot_widget(self):
        """Show the correct plot widget for the current view mode."""
        label, n_tracks, _ = _VIEW_MODES[self._view_mode_idx]
        if n_tracks == 1:
            self.plot_single.opacity = 1
            self.plot_multi.opacity = 0
        else:
            self.plot_single.opacity = 0
            self.plot_multi.opacity = 1

    # ------------------------------------------------------------------
    # View mode cycling
    # ------------------------------------------------------------------

    def _on_cycle_view(self, instance):
        self._view_mode_idx = (self._view_mode_idx + 1) % len(_VIEW_MODES)
        label, n_tracks, _ = _VIEW_MODES[self._view_mode_idx]
        self.btn_view_mode.text = f'View: {label}'

        # Rebuild multi-track widget if track count changed
        if n_tracks > 1:
            self._rebuild_multi_track(label, n_tracks)

        if self._active_tab == 'plot':
            self._show_active_plot_widget()

    def _rebuild_multi_track(self, mode_label, n_tracks):
        """Replace plot_multi with a fresh widget sized for n_tracks."""
        self._content.remove_widget(self.plot_multi)
        if mode_label.startswith('Row'):
            labels = [f'Row {i}' for i in range(n_tracks)]
        elif mode_label.startswith('Col'):
            labels = [f'Col {i}' for i in range(n_tracks)]
        else:
            labels = [f'C{i}' for i in range(n_tracks)]

        self.plot_multi = MultiTrackPlotWidget(
            track_labels=labels,
            size_hint=(1, 1), pos_hint={'x': 0, 'y': 0},
        )
        self.plot_multi.opacity = 0
        self._content.add_widget(self.plot_multi)

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
        # Quick network check on main thread — avoids a 15-second wait on wrong network
        if not self.device.is_connected_to_device_network():
            self._set_status('No device network')
            self._set_bottom(
                'Not connected to the Sessantaquattro+ WiFi. '
                'Connect to the device network and try again.'
            )
            return

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
        self.receiver_thread = DataReceiverThread(
            device=self.device,
            client_socket=self.device.client_socket,
            on_stage=self._on_data,
            on_error=lambda msg: Clock.schedule_once(
                lambda dt: self._on_receiver_error(msg), 0
            ),
            on_status=lambda msg: Clock.schedule_once(
                lambda dt: self._set_status(msg), 0
            ),
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
        self.device.stop_server()  # clean up sockets for next attempt
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
    # Data callback (receiver thread → stored for 60fps tick)
    # ------------------------------------------------------------------

    def _on_data(self, stage, data):
        """Called by the receiver thread for every processed packet."""
        # Recording — forward raw data directly on the receiver thread
        self.recording_manager.on_data_for_recording(stage, data)

        # Calibration listener
        if self._calibration_extra_callback is not None:
            self._calibration_extra_callback(stage, data)

        # Store latest data for the 60fps render tick (no Clock call needed)
        if stage == 'final':
            self._pending_data = data.copy()

            # Contraction detection (channel 0 threshold check)
            if self.is_calibrated and self.threshold is not None:
                ch0_rms = float(np.sqrt(np.mean(data[0] ** 2)))
                label = 'Contraction' if ch0_rms > self.threshold[0] else 'No Contraction'
                color = (0.2, 0.9, 0.4, 1) if ch0_rms > self.threshold[0] else (0.8, 0.3, 0.3, 1)
                Clock.schedule_once(
                    lambda dt, lbl=label, clr=color: self._update_contraction(lbl, clr), 0
                )

    def _ui_tick(self, dt):
        """60fps Kivy Clock tick — render active panel from latest data."""
        data = self._pending_data
        if data is None:
            return
        self._pending_data = None

        if self._active_tab == 'plot':
            self._render_plot_panel(data)
        else:
            self._render_heatmap_panel(data)

    def _render_plot_panel(self, data):
        label, n_tracks, agg_fn = _VIEW_MODES[self._view_mode_idx]
        if n_tracks == 1:
            self.plot_single.update(data)
            self.plot_single.render()
        else:
            if data.shape[0] < 64:
                return
            aggregated = agg_fn(data)  # (n_tracks, samples)
            for i in range(min(n_tracks, aggregated.shape[0])):
                self.plot_multi.update_track(i, aggregated[i])
            self.plot_multi.render()

    def _render_heatmap_panel(self, data):
        if data.shape[0] < 64:
            return
        # Accumulate samples into rolling buffer, compute per-channel RMS
        n = data.shape[1]
        hd = data[:64]  # (64, samples)
        for i in range(n):
            idx = self._heatmap_buf_idx % 100
            self._heatmap_buffer[:, idx] = hd[:, i]
            self._heatmap_buf_idx += 1

        rms = np.sqrt(np.mean(self._heatmap_buffer ** 2, axis=1))  # (64,)

        if self.is_calibrated and self.mvc_rms is not None:
            mvc = self.mvc_rms[:64]
            mvc = np.where(mvc > 0, mvc, 1.0)
            normalized = np.clip(rms / mvc, 0.0, 1.0)
        else:
            peak = rms.max()
            normalized = rms / peak if peak > 0 else rms

        self.heatmap.update(normalized)

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
        Clock.schedule_once(
            lambda dt: self._set_bottom('Recording stopped: max samples reached.'), 0
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, text):
        self.status_label.text = text

    def _set_bottom(self, text):
        self.bottom_label.text = text

    def _on_status_update(self, text):
        Clock.schedule_once(lambda dt: self._set_status(text), 0)
