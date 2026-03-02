"""Post-session data analysis screen."""

import csv
import threading
import numpy as np

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.clock import Clock

from app.processing.features import (
    compute_tkeo_activation_timing,
    compute_burst_duration,
    compute_fatigue,
    compute_bilateral_symmetry,
    compute_centroid_shift,
    compute_spatial_nonuniformity,
)


def _load_csv(filepath):
    """Load a recording CSV into (timestamps, data) arrays.

    Returns:
        (timestamps: np.ndarray shape (N,), data: np.ndarray shape (channels, N))
        or (None, None) on failure.
    """
    try:
        with open(filepath, newline='') as f:
            reader = csv.reader(f)
            headers = next(reader)
            rows = [list(map(float, row)) for row in reader]

        if not rows:
            return None, None

        arr = np.array(rows)
        timestamps = arr[:, 0]
        data = arr[:, 1:].T  # (channels, samples)
        return timestamps, data

    except Exception as e:
        print(f"[DataAnalysis] CSV load error: {e}")
        return None, None


def _estimated_fs(timestamps):
    """Estimate sample rate from timestamps."""
    if len(timestamps) < 2:
        return 2000.0
    dt = np.diff(timestamps)
    dt = dt[dt > 0]
    return float(1.0 / np.median(dt)) if len(dt) > 0 else 2000.0


class DataAnalysisScreen(Screen):
    """Offline post-session analysis screen.

    Equivalent to the desktop's DataAnalysisWindow. Allows loading one or two
    CSV recording files and running all feature analyses from features.py.
    Results are displayed as scrollable text; plots open in separate popups.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Loaded recording state
        self._file1 = None
        self._ts1 = None
        self._data1 = None
        self._file2 = None
        self._ts2 = None
        self._data2 = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = BoxLayout(orientation='vertical')

        # Top bar
        top_bar = BoxLayout(orientation='horizontal', size_hint=(1, 0.08), padding=4, spacing=4)
        btn_back = Button(text='Back', size_hint=(0.1, 1))
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'selection'))
        top_bar.add_widget(btn_back)
        top_bar.add_widget(Label(text='Data Analysis', font_size=20, bold=True, size_hint=(0.6, 1)))
        root.add_widget(top_bar)

        # File load bar
        file_bar = BoxLayout(orientation='horizontal', size_hint=(1, 0.08), padding=4, spacing=4)

        self.file1_label = Label(text='No file loaded', size_hint=(0.35, 1), font_size=12,
                                 color=(0.7, 0.7, 0.7, 1))
        btn_load1 = Button(text='Load File 1', size_hint=(0.15, 1))
        btn_load1.bind(on_press=lambda x: self._show_file_chooser(1))

        self.file2_label = Label(text='No file 2 (for bilateral symmetry)',
                                 size_hint=(0.35, 1), font_size=12, color=(0.7, 0.7, 0.7, 1))
        btn_load2 = Button(text='Load File 2', size_hint=(0.15, 1))
        btn_load2.bind(on_press=lambda x: self._show_file_chooser(2))

        file_bar.add_widget(btn_load1)
        file_bar.add_widget(self.file1_label)
        file_bar.add_widget(btn_load2)
        file_bar.add_widget(self.file2_label)
        root.add_widget(file_bar)

        # Analysis buttons
        btn_grid = GridLayout(cols=3, size_hint=(1, 0.12), padding=4, spacing=4)
        analyses = [
            ('Activation Timing', self._run_tkeo),
            ('Burst Duration', self._run_burst),
            ('Fatigue', self._run_fatigue),
            ('Bilateral Symmetry', self._run_bilateral),
            ('Centroid Shift', self._run_centroid),
            ('Spatial Uniformity', self._run_spatial),
        ]
        for label, handler in analyses:
            btn = Button(text=label, font_size=13)
            btn.bind(on_press=handler)
            btn_grid.add_widget(btn)
        root.add_widget(btn_grid)

        # Results area (scrollable)
        scroll = ScrollView(size_hint=(1, 0.72))
        self.results_label = Label(
            text='Load a recording file and run an analysis.',
            font_size=13,
            halign='left',
            valign='top',
            size_hint_y=None,
            text_size=(None, None),
        )
        self.results_label.bind(
            texture_size=lambda inst, val: setattr(inst, 'size', val)
        )
        scroll.add_widget(self.results_label)
        root.add_widget(scroll)

        self.add_widget(root)

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def _show_file_chooser(self, slot):
        """Open a file chooser popup for the given slot (1 or 2)."""
        from app.core.paths import get_recordings_dir
        import os

        start_path = get_recordings_dir() if os.path.isdir(get_recordings_dir()) else '/'

        content = BoxLayout(orientation='vertical')
        chooser = FileChooserListView(
            path=start_path,
            filters=['*.csv'],
            size_hint=(1, 0.85),
        )
        btn_bar = BoxLayout(size_hint=(1, 0.15), spacing=8)
        btn_select = Button(text='Select')
        btn_cancel = Button(text='Cancel')
        btn_bar.add_widget(btn_select)
        btn_bar.add_widget(btn_cancel)
        content.add_widget(chooser)
        content.add_widget(btn_bar)

        popup = Popup(title=f'Select File {slot}', content=content, size_hint=(0.9, 0.85))

        def on_select(inst):
            if chooser.selection:
                self._load_file(slot, chooser.selection[0])
            popup.dismiss()

        btn_select.bind(on_press=on_select)
        btn_cancel.bind(on_press=lambda x: popup.dismiss())
        popup.open()

    def _load_file(self, slot, path):
        """Load a CSV file into slot 1 or 2."""
        import os
        name = os.path.basename(path)
        self._set_results(f'Loading {name}...')

        def load():
            ts, data = _load_csv(path)
            Clock.schedule_once(lambda dt: self._on_file_loaded(slot, path, name, ts, data), 0)

        threading.Thread(target=load, daemon=True).start()

    def _on_file_loaded(self, slot, path, name, ts, data):
        if ts is None:
            self._set_results(f'Failed to load {name}. Check file format.')
            return

        if slot == 1:
            self._file1, self._ts1, self._data1 = path, ts, data
            self.file1_label.text = f'{name} ({data.shape[0]} ch, {data.shape[1]} samples)'
        else:
            self._file2, self._ts2, self._data2 = path, ts, data
            self.file2_label.text = f'{name} ({data.shape[0]} ch, {data.shape[1]} samples)'

        self._set_results(f'Loaded {name} into slot {slot}.')

    # ------------------------------------------------------------------
    # Analysis runners
    # ------------------------------------------------------------------

    def _require_file1(self):
        if self._data1 is None:
            self._set_results('Load a recording file first.')
            return False
        return True

    def _run_tkeo(self, instance):
        if not self._require_file1():
            return
        self._set_results('Running activation timing analysis...')

        def run():
            ch0 = self._data1[0]
            fs = _estimated_fs(self._ts1)
            result = compute_tkeo_activation_timing(ch0, self._ts1, fs)
            if result is None:
                text = 'Activation timing: analysis failed (check data quality).'
            else:
                n = len(result.onset_times)
                times = ', '.join(f'{t:.2f}s' for t in result.onset_times[:10])
                suffix = '...' if n > 10 else ''
                text = (
                    f'Activation Timing (TKEO) — Channel 1\n'
                    f'  Onsets detected: {n}\n'
                    f'  Detection threshold: {result.detection_threshold:.4f}\n'
                    f'  Sample rate: {result.sample_rate:.0f} Hz\n'
                    f'  Onset times: {times}{suffix}'
                )
            Clock.schedule_once(lambda dt: self._set_results(text), 0)

        threading.Thread(target=run, daemon=True).start()

    def _run_burst(self, instance):
        if not self._require_file1():
            return
        self._set_results('Running burst duration analysis...')

        def run():
            ch0 = self._data1[0]
            fs = _estimated_fs(self._ts1)
            result = compute_burst_duration(ch0, self._ts1, fs)
            if result is None:
                text = 'Burst duration: analysis failed.'
            else:
                text = (
                    f'Burst Duration — Channel 1\n'
                    f'  Bursts detected: {result.num_bursts}\n'
                    f'  Average duration: {result.avg_duration:.3f} s\n'
                    f'  Std deviation: {result.std_duration:.3f} s'
                )
                if result.num_bursts > 0:
                    durs = ', '.join(f'{d:.3f}s' for d in result.burst_durations[:8])
                    text += f'\n  Individual durations: {durs}'
            Clock.schedule_once(lambda dt: self._set_results(text), 0)

        threading.Thread(target=run, daemon=True).start()

    def _run_fatigue(self, instance):
        if not self._require_file1():
            return
        self._set_results('Running fatigue analysis...')

        def run():
            ch0 = self._data1[0]
            fs = _estimated_fs(self._ts1)
            result = compute_fatigue(ch0, self._ts1, fs)
            if result is None:
                text = 'Fatigue: analysis failed.'
            else:
                rms_onset = (
                    f'{result.time_to_rms_fatigue[0]:.2f} s'
                    if result.time_to_rms_fatigue is not None else 'Not detected'
                )
                mf_onset = (
                    f'{result.time_to_mf_fatigue[0]:.2f} s'
                    if result.time_to_mf_fatigue is not None else 'Not detected'
                )
                text = (
                    f'Fatigue Analysis — Channel 1\n'
                    f'  Baseline RMS: {result.baseline_rms:.4f}\n'
                    f'  RMS fatigue onset: {rms_onset}\n'
                    f'    (threshold: +{result.rms_threshold*100:.1f}% increase)\n'
                    f'  Median frequency fatigue onset: {mf_onset}\n'
                    f'    (threshold: {result.mf_threshold:.2f} Hz/s decline)'
                )
            Clock.schedule_once(lambda dt: self._set_results(text), 0)

        threading.Thread(target=run, daemon=True).start()

    def _run_bilateral(self, instance):
        if self._data1 is None or self._data2 is None:
            self._set_results('Load both File 1 and File 2 for bilateral symmetry.')
            return
        self._set_results('Running bilateral symmetry analysis...')

        def run():
            ch0_1 = self._data1[0]
            ch0_2 = self._data2[0]
            fs1 = _estimated_fs(self._ts1)
            fs2 = _estimated_fs(self._ts2)
            result = compute_bilateral_symmetry(ch0_1, self._ts1, fs1, ch0_2, self._ts2, fs2)
            if result is None:
                text = 'Bilateral symmetry: analysis failed.'
            else:
                text = (
                    f'Bilateral Symmetry Index — Channel 1\n'
                    f'  Mean SI: {result.mean_si:.4f}  '
                    f'(0 = symmetric, +1 = file1 dominant, -1 = file2 dominant)\n'
                    f'  Std SI: {result.std_si:.4f}\n'
                    f'  Max asymmetry: {result.max_asymmetry:.4f}\n'
                    f'  File 1 overall RMS: {result.rms_file1:.4f}\n'
                    f'  File 2 overall RMS: {result.rms_file2:.4f}\n'
                    f'  Overlap duration: {result.overlap_duration:.2f} s'
                )
            Clock.schedule_once(lambda dt: self._set_results(text), 0)

        threading.Thread(target=run, daemon=True).start()

    def _run_centroid(self, instance):
        if not self._require_file1():
            return
        if self._data1.shape[0] < 64:
            self._set_results(
                f'Centroid shift requires 64-channel HD-EMG data. '
                f'File has {self._data1.shape[0]} channels.'
            )
            return
        self._set_results('Running centroid shift analysis...')

        def run():
            fs = _estimated_fs(self._ts1)
            result = compute_centroid_shift(self._data1[:64], self._ts1, fs)
            if result is None:
                text = 'Centroid shift: analysis failed.'
            else:
                text = (
                    f'Centroid Shift (HD-EMG 8x8 grid)\n'
                    f'  Initial centroid: ({result.initial_centroid[0]:.2f}, '
                    f'{result.initial_centroid[1]:.2f})\n'
                    f'  Total shift: {result.total_shift:.3f} electrode-units\n'
                    f'  Mean drift rate: {result.mean_drift_rate:.4f} electrode-units/s\n'
                    f'  Windows analyzed: {len(result.times)}'
                )
            Clock.schedule_once(lambda dt: self._set_results(text), 0)

        threading.Thread(target=run, daemon=True).start()

    def _run_spatial(self, instance):
        if not self._require_file1():
            return
        if self._data1.shape[0] < 64:
            self._set_results(
                f'Spatial non-uniformity requires 64-channel HD-EMG data. '
                f'File has {self._data1.shape[0]} channels.'
            )
            return
        self._set_results('Running spatial non-uniformity analysis...')

        def run():
            fs = _estimated_fs(self._ts1)
            result = compute_spatial_nonuniformity(self._data1[:64], self._ts1, fs)
            if result is None:
                text = 'Spatial non-uniformity: analysis failed.'
            else:
                text = (
                    f'Spatial Non-Uniformity (HD-EMG 8x8 grid)\n'
                    f'  Threshold source: {result.threshold_source}\n'
                    f'  Mean CV (coefficient of variation): {np.mean(result.cv):.4f}\n'
                    f'    Higher = more spatially uneven activation\n'
                    f'  Mean Shannon entropy: {np.mean(result.entropy):.4f} bits '
                    f'(max 6.0 for 64 channels)\n'
                    f'    Higher = more uniform distribution\n'
                    f'  Mean activation fraction: {np.mean(result.activation_fraction):.3f} '
                    f'({np.mean(result.activation_fraction)*100:.1f}% of channels active)\n'
                    f'  Windows analyzed: {len(result.times)}'
                )
            Clock.schedule_once(lambda dt: self._set_results(text), 0)

        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_results(self, text):
        self.results_label.text = text
        self.results_label.text_size = (self.results_label.width, None)
