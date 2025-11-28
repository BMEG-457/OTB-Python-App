class Config:
    # ==========================================
    # DISPLAY AND UI CONFIGURATION
    # ==========================================
    DEFAULT_PLOT_TIME = 1      # seconds - default time window for plots
    UPDATE_RATE = 16          # milliseconds - timer interval (~62.5 FPS)
    PLOT_HEIGHT = 600         # pixels - minimum height for track plots
    WINDOW_SIZE = (1200, 800) # (width, height) - main window size
    
    # Layout stretch factors
    CONTENT_STRETCH = 3       # stretch factor for main content areas
    PANEL_STRETCH = 0         # stretch factor for control panels
    
    # Grid display parameters
    GRID_ALPHA = 0.3          # grid transparency
    PLOT_WIDTH = 1            # line width for plots
    
    # ==========================================
    # DEVICE COMMUNICATION
    # ==========================================
    DEFAULT_HOST = "0.0.0.0"  # server host address
    DEFAULT_PORT = 45454      # communication port
    DEFAULT_NCHANNELS = 72    # default number of channels
    DEFAULT_FREQUENCY = 2000  # default sampling frequency (Hz)
    CONNECTION_TIMEOUT = 10   # seconds - timeout for device connection
    
    # Device network configuration
    DEVICE_NETWORK_PREFIX = "192.168.1"  # WiFi network prefix for device
    
    # Data packet configuration
    FPS_CALCULATION_INTERVAL = 100  # packets between FPS calculations
    
    # ==========================================
    # DEVICE COMMAND DEFAULTS
    # ==========================================
    # Default command parameters for Sessantaquattro+
    DEFAULT_FSAMP = 2         # Sampling frequency (0=500Hz, 1=1kHz, 2=2kHz, 3=4kHz)
    DEFAULT_NCH = 3           # Number of channels (0=8, 1=16, 2=32, 3=64)
    DEFAULT_MODE = 0          # Working mode (0=Monopolar, 1=Bipolar, etc.)
    DEFAULT_HRES = 0          # High resolution (0=16bit, 1=24bit)
    DEFAULT_HPF = 1           # High pass filter (0=DC, 1=10.5Hz)
    DEFAULT_EXTEN = 0         # Extension factor
    DEFAULT_TRIG = 0          # Trigger mode (0=GO/STOP, 1=internal, 2=external, 3=button)
    DEFAULT_REC = 0           # Recording on SD (0=stop, 1=rec)
    DEFAULT_GO = 1            # Data transfer (0=stop, 1=go)
    
    # Channel count mapping based on NCH and MODE
    CHANNEL_MAPPING = {
        (0, 0): 16, (0, 1): 12,  # 8 channels
        (1, 0): 24, (1, 1): 16,  # 16 channels
        (2, 0): 40, (2, 1): 24,  # 32 channels
        (3, 0): 72, (3, 1): 40,  # 64 channels
    }
    
    # ==========================================
    # SIGNAL PROCESSING
    # ==========================================
    # Filter parameters
    BANDPASS_LOW = 20         # Hz - low cutoff for bandpass filter
    BANDPASS_HIGH = 450       # Hz - high cutoff for bandpass filter
    NOTCH_FREQ = 60          # Hz - notch filter frequency (powerline interference)
    
    # Feature extraction window
    RMS_WINDOW_SIZE = 100     # samples for RMS calculation
    
    # Saturation thresholds for 16-bit data
    SATURATION_LOW = -32760   # close to int16 minimum (-32768)
    SATURATION_HIGH = 32760   # close to int16 maximum (32767)
    
    # ==========================================
    # TRACK CONFIGURATION
    # ==========================================
    # Track conversion factors and offsets
    HDSEMG_OFFSET = 0.001
    HDSEMG_CONV_FACTOR = 0.000000286
    
    AUX_OFFSET = 1
    AUX_CONV_FACTOR = 0.00014648
    
    QUAT_OFFSET = 1
    QUAT_CONV_FACTOR = 1
    
    BUFFER_OFFSET = 1
    BUFFER_CONV_FACTOR = 1
    
    RAMP_OFFSET = 1
    RAMP_CONV_FACTOR = 1
    
    # Track layout parameters
    TRACK_MIN_HEIGHT = 300    # pixels - minimum height for track widgets
    
    # Legend configuration
    MAX_LEGEND_CHANNELS = 8   # maximum channels to show in legend
    
    # ==========================================
    # CALIBRATION SETTINGS
    # ==========================================
    # Default calibration durations
    DEFAULT_REST_DURATION = 5        # seconds
    DEFAULT_CONTRACTION_DURATION = 5 # seconds
    
    # Calibration thresholds
    MIN_CALIBRATION_SAMPLES = 1      # minimum required samples for calibration
    BASELINE_MULTIPLIER = 3.0        # threshold = baseline + 3.0 * std
    
    # ==========================================
    # RECORDING SETTINGS
    # ==========================================
    MAX_RECORDING_SAMPLES = 1000000  # maximum samples to record in memory
    
    # ==========================================
    # CONTRACTION DETECTION
    # ==========================================
    # Default parameters for contraction detection
    RATE_THRESHOLD = 0.001           # V/s - rate of change threshold
    MIN_DURATION_SAMPLES = 5         # minimum contraction duration in samples
    SMOOTHING_WINDOW = 3             # samples for smoothing
    HYSTERESIS_FACTOR = 0.6          # offset threshold factor
    REFRACTORY_PERIOD_FACTOR = 0.3   # refractory period as fraction of min duration
    
    # ==========================================
    # HEATMAP CONFIGURATION
    # ==========================================
    HEATMAP_SIZE = (8, 8)           # dimensions of HD-EMG array
    HEATMAP_CHANNELS = 64           # number of channels in heatmap
    HEATMAP_COLORMAP = 'viridis'    # default colormap
    HEATMAP_LEVELS = (0, 1)         # color scale range
    
    # ==========================================
    # FONT AND TEXT SETTINGS
    # ==========================================
    INSTRUCTION_FONT_SIZE = 14      # pixels
    TIMER_FONT_SIZE = 32           # pixels
    TIMER_COLOR = "red"            # color for countdown timer
    
    # ==========================================
    # PERFORMANCE SETTINGS
    # ==========================================
    # Background color for plots
    PLOT_BACKGROUND_COLOR = (30, 30, 30)  # RGB values
    
    # Anti-aliasing settings
    ENABLE_ANTIALIASING = True
    
    # Auto-range settings
    ENABLE_AUTO_RANGE = True