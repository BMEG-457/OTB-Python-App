import json
from app.core.paths import get_config_path


def _load():
    try:
        with open(get_config_path(), 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


_cfg = _load()


class Config:
    # Device
    _dev = _cfg.get("device", {})
    DEVICE_HOST             = _dev.get("host", "0.0.0.0")
    DEVICE_GATEWAY_IP       = _dev.get("gateway_ip", "192.168.1.1")
    DEVICE_PORT             = _dev.get("port", 45454)
    DEVICE_NETWORK_PREFIX   = _dev.get("network_prefix", "192.168.1")
    CONNECTION_TIMEOUT      = _dev.get("connection_timeout_s", 10)
    SOCKET_TIMEOUT          = _dev.get("socket_timeout_s", 5.0)
    DEFAULT_FSAMP           = _dev.get("default_fsamp", 2)
    DEFAULT_NCH             = _dev.get("default_nch", 3)
    DEFAULT_MODE            = _dev.get("default_mode", 0)
    DEFAULT_HPF             = _dev.get("default_hpf", 1)
    DEFAULT_HRES            = _dev.get("default_hres", 0)
    PACKET_SIZE_DIVISOR     = _dev.get("packet_size_divisor", 16)
    FPS_LOG_INTERVAL        = _dev.get("fps_log_interval", 100)

    # Recording / saturation
    _rec = _cfg.get("recording", {})
    MAX_RECORDING_SAMPLES   = _rec.get("max_samples", 1000000)
    SATURATION_LOW          = _rec.get("saturation_low", -32760)
    SATURATION_HIGH         = _rec.get("saturation_high", 32760)

    # Signal processing
    _sig = _cfg.get("signal", {})
    BANDPASS_LOW            = _sig.get("bandpass_low_hz", 20)
    BANDPASS_HIGH           = _sig.get("bandpass_high_hz", 450)
    NOTCH_FREQ              = _sig.get("notch_freq_hz", 60)
    FILTER_ORDER            = _sig.get("filter_order", 4)
    FILTER_ORDER_SMALL      = _sig.get("filter_order_small", 1)
    FILTER_MIN_SAMPLES      = _sig.get("filter_min_samples", 10)
    NOTCH_QUALITY           = _sig.get("notch_quality", 30)
    NOTCH_MIN_SAMPLES       = _sig.get("notch_min_samples", 15)

    # Contraction detection
    _det = _cfg.get("detection", {})
    ON_THRESHOLD            = _det.get("on_threshold", 0.15)
    OFF_THRESHOLD           = _det.get("off_threshold", 0.08)

    # Calibration
    _cal = _cfg.get("calibration", {})
    REST_DURATION           = _cal.get("rest_duration_s", 5)
    CONTRACTION_DURATION    = _cal.get("contraction_duration_s", 5)
    MVC_PERCENTILE          = _cal.get("mvc_percentile", 99)
    BASELINE_THRESHOLD_MULT = _cal.get("baseline_threshold_multiplier", 3.0)
    BAD_CHANNEL_FRACTION    = _cal.get("bad_channel_mvc_fraction", 0.1)
    MIN_CAL_SAMPLES         = _cal.get("min_calibration_samples", 1)

    # UI / display
    _ui = _cfg.get("ui", {})
    WINDOW_SIZE             = (_ui.get("window_width", 1200), _ui.get("window_height", 800))
    UPDATE_RATE             = _ui.get("update_rate_ms", 16)
    PLOT_HEIGHT             = _ui.get("plot_height", 600)
    DEFAULT_PLOT_TIME       = _ui.get("default_plot_time_s", 1)
    FEATURE_RATE            = _ui.get("feature_rate_hz", 30)
    FEATURE_PLOT_TIME       = _ui.get("feature_plot_history_s", 10)
    FEATURE_WINDOW_MS       = _ui.get("feature_window_ms", 200)
    FEATURE_PLOT_MIN_HEIGHT = _ui.get("feature_plot_min_height", 200)
    TRACK_MIN_HEIGHT        = _ui.get("track_min_height", 300)
    GROUP_TRACK_MIN_HEIGHT  = _ui.get("group_track_min_height", 200)
    CONTROL_PANEL_WIDTH     = _ui.get("control_panel_width", 200)
    INIT_DELAY_MS           = _ui.get("init_delay_ms", 100)
    RECEIVER_WAIT_MS        = _ui.get("receiver_wait_timeout_ms", 2000)
    CONTRACTION_RATE_WINDOW = _ui.get("contraction_rate_window_s", 60.0)
    RMS_WINDOW_DEFAULT      = _ui.get("rms_window_default", 50)
    LP_CUTOFF_DEFAULT       = _ui.get("lp_cutoff_default_hz", 10)
    _colors = _ui.get("colors", {})
    COLOR_LED_INACTIVE      = _colors.get("led_inactive", "#808080")
    COLOR_LED_CONTRACTING   = _colors.get("led_contracting", "#FF4444")
    COLOR_LED_RELAXED       = _colors.get("led_relaxed", "#00CC44")
    COLOR_TRACK_BG          = tuple(_colors.get("track_background", [30, 30, 30]))
    COLOR_CURVE             = tuple(_colors.get("curve_default", [255, 255, 255]))
    _sym = _ui.get("symmetry_thresholds", {})
    SYMMETRY_GOOD           = _sym.get("good", 0.1)
    SYMMETRY_MODERATE       = _sym.get("moderate", 0.25)
    SYMMETRY_POOR           = _sym.get("poor", 0.5)
    ANALYSIS_WINDOW_DEFAULT = _ui.get("analysis_window_default_s", 5.0)

    # HD-EMG grid
    _hd = _cfg.get("hdemg", {})
    EMG_CHANNELS            = _hd.get("emg_channels", 64)
    GRID_ROWS               = _hd.get("grid_rows", 8)
    GRID_COLS               = _hd.get("grid_cols", 8)
    CHANNEL_NAMING_MAX      = _hd.get("channel_naming_max", 8)
    CURVE_LINE_WIDTH        = _hd.get("curve_line_width", 1)

    # Feature extraction defaults
    _feat = _cfg.get("features", {})
    _tkeo = _feat.get("tkeo", {})
    TKEO_BANDPASS_LOW       = _tkeo.get("bandpass_low_hz", 20.0)
    TKEO_BANDPASS_HIGH      = _tkeo.get("bandpass_high_hz", 450.0)
    TKEO_SMOOTH_CUTOFF      = _tkeo.get("smooth_cutoff_hz", 10.0)
    TKEO_BASELINE_DURATION  = _tkeo.get("baseline_duration_s", 0.5)
    TKEO_K_THRESHOLD        = _tkeo.get("k_threshold", 8.0)
    TKEO_AMP_DIVISOR        = _tkeo.get("amplitude_divisor", 4.0)
    TKEO_MIN_PEAK_DIST      = _tkeo.get("min_peak_distance_s", 0.5)
    TKEO_BACKTRACK_K        = _tkeo.get("backtrack_k", 3.0)
    TKEO_MIN_DATA_LEN       = _tkeo.get("min_data_length", 30)
    BURST_MIN_DURATION      = _feat.get("burst_duration", {}).get("min_duration_s", 0.05)
    BILATERAL_WINDOW        = _feat.get("bilateral_symmetry", {}).get("window_s", 0.25)
    BILATERAL_STEP          = _feat.get("bilateral_symmetry", {}).get("step_s", 0.05)
    FATIGUE_RMS_THRESHOLD   = _feat.get("fatigue", {}).get("rms_threshold", 0.317)
    FATIGUE_MF_THRESHOLD    = _feat.get("fatigue", {}).get("mf_threshold", -0.89)
    FATIGUE_WINDOW          = _feat.get("fatigue", {}).get("window_s", 0.5)
    FATIGUE_STEP            = _feat.get("fatigue", {}).get("step_s", 0.1)
    FATIGUE_BASELINE        = _feat.get("fatigue", {}).get("baseline_duration_s", 0.5)
    CENTROID_WINDOW         = _feat.get("centroid_shift", {}).get("window_s", 0.5)
    CENTROID_STEP           = _feat.get("centroid_shift", {}).get("step_s", 0.1)
    SPNU_WINDOW             = _feat.get("spatial_nonuniformity", {}).get("window_s", 0.5)
    SPNU_STEP               = _feat.get("spatial_nonuniformity", {}).get("step_s", 0.1)
    SPNU_EPSILON            = _feat.get("spatial_nonuniformity", {}).get("entropy_epsilon", 1e-12)
