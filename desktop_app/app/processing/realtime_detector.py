"""Real-time contraction detection for live EMG streaming."""

import numpy as np

from app.core.config import Config


class ContractionDetector:
    """Detects muscle contractions from normalized per-channel RMS values.

    Uses hysteresis to prevent flickering:
    - Contraction triggers when mean normalized activation exceeds ON_THRESHOLD
    - Contraction releases when mean normalized activation drops below OFF_THRESHOLD
    """

    ON_THRESHOLD = Config.ON_THRESHOLD
    OFF_THRESHOLD = Config.OFF_THRESHOLD

    def __init__(self):
        self.is_contracting = False

    def update(self, normalized_rms: np.ndarray) -> bool:
        """Feed normalized per-channel RMS and update contraction state.

        Args:
            normalized_rms: Array of per-channel RMS values normalized to MVC, clipped [0, 1].

        Returns:
            True if the contraction state changed, False otherwise.
        """
        mean_activation = np.mean(normalized_rms)
        old_state = self.is_contracting

        if not self.is_contracting and mean_activation > self.ON_THRESHOLD:
            self.is_contracting = True
        elif self.is_contracting and mean_activation < self.OFF_THRESHOLD:
            self.is_contracting = False

        return self.is_contracting != old_state

    def reset(self):
        """Reset to non-contracting state."""
        self.is_contracting = False
