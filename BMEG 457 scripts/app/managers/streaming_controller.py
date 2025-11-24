"""Streaming controller for managing live data viewing."""

from PyQt5 import QtCore


class StreamingController(QtCore.QObject):
    """Manages streaming state and receiver thread interactions."""
    
    # Signals for status updates
    status_update = QtCore.pyqtSignal(str)
    
    def __init__(self, timer, receiver_thread):
        super().__init__()
        self.timer = timer
        self.receiver_thread = receiver_thread
        self.is_streaming = False
        self.is_paused = False
    
    def start_streaming(self):
        """Start live streaming without recording."""
        self.is_streaming = True
        self.is_paused = False
        self.timer.start()
        if self.receiver_thread is not None:
            self.receiver_thread.running = True
        self.status_update.emit("Streaming...")
        print("Live streaming started")
        return True
    
    def stop_streaming(self):
        """Stop live streaming."""
        self.is_streaming = False
        self.is_paused = True
        self.timer.stop()
        if self.receiver_thread is not None:
            self.receiver_thread.running = False
        self.status_update.emit("Stream stopped")
        print("Live streaming stopped")
        return True
    
    def toggle_streaming(self):
        """Toggle streaming state on/off."""
        if self.is_streaming:
            return self.stop_streaming()
        else:
            return self.start_streaming()
    
    def pause_streaming(self):
        """Pause streaming temporarily."""
        self.is_paused = True
        self.timer.stop()
        return True
    
    def resume_streaming(self):
        """Resume paused streaming."""
        self.is_paused = False
        self.timer.start()
        return True
    
    def get_streaming_state(self):
        """Get current streaming state.
        
        Returns:
            dict: Dictionary with streaming status information
        """
        return {
            'is_streaming': self.is_streaming,
            'is_paused': self.is_paused
        }
