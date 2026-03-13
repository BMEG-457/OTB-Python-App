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
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.metrics import sp

from app.core import config as CFG
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
    fallback = float(CFG.DEVICE_SAMPLE_RATE)
    if len(timestamps) < 2:
        return fallback
    dt = np.diff(timestamps)
    dt = dt[dt > 0]
    return float(1.0 / np.median(dt)) if len(dt) > 0 else fallback


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
        btn_back = Button(text='Back', size_hint=(0.1, 1), font_size=sp(16))
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'selection'))
        top_bar.add_widget(btn_back)
        top_bar.add_widget(Label(text='Data Analysis', font_size=sp(22), bold=True, size_hint=(0.6, 1)))
        root.add_widget(top_bar)

        # File load bar
        file_bar = BoxLayout(orientation='horizontal', size_hint=(1, 0.08), padding=4, spacing=4)

        self.file1_label = Label(text='No file loaded', size_hint=(0.35, 1), font_size=sp(14),
                                 color=(0.7, 0.7, 0.7, 1))
        btn_load1 = Button(text='Load File 1', size_hint=(0.15, 1), font_size=sp(15))
        btn_load1.bind(on_press=lambda x: self._show_file_chooser(1))

        self.file2_label = Label(text='No file 2 (for bilateral symmetry)',
                                 size_hint=(0.35, 1), font_size=sp(14), color=(0.7, 0.7, 0.7, 1))
        btn_load2 = Button(text='Load File 2', size_hint=(0.15, 1), font_size=sp(15))
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
            btn = Button(text=label, font_size=sp(15))
            btn.bind(on_press=handler)
            btn_grid.add_widget(btn)
        root.add_widget(btn_grid)

        # Results area (scrollable)
        scroll = ScrollView(size_hint=(1, 0.72))
        self.results_label = Label(
            text='Load a recording file and run an analysis.',
            font_size=sp(15),
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
        """Navigable file browser popup starting at /sdcard/Documents.

        Shows subdirectories and CSV files.  Tap a directory to enter it;
        tap a CSV to select it.  A '[..] Up' row returns to the parent.
        """
        import os

        # Test actual readability — os.path.isdir can succeed even when
        # os.listdir is denied (different syscalls, different permission checks).
        # user_data_dir (private internal storage) is always accessible and is
        # where recordings fall back to if external storage permission is not
        # yet in effect (requires app restart after grant).
        package = CFG.ANDROID_PACKAGE_NAME

        # Try Android API first — may succeed where direct POSIX access is blocked.
        _jnius_ext = None
        try:
            from jnius import autoclass as _ac
            _ext = _ac('org.kivy.android.PythonActivity').mActivity.getExternalFilesDir(None)
            if _ext is not None:
                _jnius_ext = _ext.getAbsolutePath()
        except Exception:
            pass

        try:
            from kivy.app import App as _App
            _udd = _App.get_running_app().user_data_dir
        except Exception:
            _udd = None

        start_dir = None
        for candidate in filter(None, (
            _jnius_ext,
            f'/storage/emulated/0/Android/data/{package}/files',
            '/storage/emulated/0/Documents',
            '/sdcard/Documents',
            '/storage/emulated/0',
            '/sdcard',
            _udd,
        )):
            try:
                os.listdir(candidate)
                start_dir = candidate
                break
            except Exception:
                continue

        content = BoxLayout(orientation='vertical', spacing=4, padding=4)

        if start_dir is None:
            # No accessible path found — storage permission not yet in effect.
            # User must close and reopen the app after granting permission.
            content = BoxLayout(orientation='vertical', padding=16, spacing=12)
            content.add_widget(Label(
                text=(
                    'Storage not accessible.\n\n'
                    'If you just granted the storage permission,\n'
                    'close and reopen the app for it to take effect.\n\n'
                    'Recordings are saved to:\n'
                    'Android > data > org.bmeg457.otbemgapp\n'
                    '> files > OTB_EMG > recordings'
                ),
                font_size=sp(15), halign='center', valign='middle',
                size_hint=(1, 0.88),
            ))
            btn_cancel2 = Button(text='OK', font_size=sp(16), size_hint=(1, 0.12))
            popup2 = Popup(
                title='Storage unavailable', content=content,
                size_hint=(0.85, 0.55),
            )
            btn_cancel2.bind(on_press=lambda x: popup2.dismiss())
            content.add_widget(btn_cancel2)
            popup2.open()
            return

        path_label = Label(
            text=start_dir, font_size=sp(12), size_hint=(1, None), height=sp(28),
            halign='left', color=(0.5, 0.75, 1, 1),
        )
        path_label.bind(size=lambda inst, _: setattr(inst, 'text_size', (inst.width, None)))
        content.add_widget(path_label)

        scroll = ScrollView(size_hint=(1, 0.82))
        file_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=2)
        file_list.bind(minimum_height=file_list.setter('height'))
        scroll.add_widget(file_list)
        content.add_widget(scroll)

        btn_cancel = Button(text='Cancel', font_size=sp(16), size_hint=(1, 0.1))
        content.add_widget(btn_cancel)

        popup = Popup(title=f'Select File {slot}', content=content, size_hint=(0.92, 0.92))
        btn_cancel.bind(on_press=lambda x: popup.dismiss())

        def populate(directory):
            file_list.clear_widgets()
            path_label.text = directory

            # Up-one-level row
            parent = os.path.dirname(directory)
            if parent and parent != directory:
                up_btn = Button(
                    text='[..] Up', font_size=sp(15),
                    size_hint_y=None, height=sp(48),
                    background_color=(0.25, 0.30, 0.45, 1),
                )
                up_btn.bind(on_press=lambda x, p=parent: populate(p))
                file_list.add_widget(up_btn)

            try:
                entries = sorted(os.listdir(directory))
            except Exception as e:
                file_list.add_widget(Label(
                    text=f'Cannot read folder:\n{e}',
                    font_size=sp(14), size_hint_y=None, height=sp(60),
                ))
                return

            dirs = [e for e in entries if os.path.isdir(os.path.join(directory, e))
                    and not e.startswith('.')]
            csvs = [e for e in entries if e.lower().endswith('.csv')]

            for d in dirs:
                dpath = os.path.join(directory, d)
                btn = Button(
                    text=f'[{d}/]', font_size=sp(15),
                    size_hint_y=None, height=sp(48),
                    background_color=(0.22, 0.32, 0.50, 1),
                )
                btn.bind(on_press=lambda x, p=dpath: populate(p))
                file_list.add_widget(btn)

            for fname in csvs:
                fpath = os.path.join(directory, fname)
                btn = Button(
                    text=fname, font_size=sp(14),
                    size_hint_y=None, height=sp(48),
                )
                btn.bind(on_press=lambda x, p=fpath: (self._load_file(slot, p), popup.dismiss()))
                file_list.add_widget(btn)

            if not dirs and not csvs:
                file_list.add_widget(Label(
                    text='No folders or CSV files here.',
                    font_size=sp(14), size_hint_y=None, height=sp(48),
                    halign='center',
                ))

        populate(start_dir)
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
