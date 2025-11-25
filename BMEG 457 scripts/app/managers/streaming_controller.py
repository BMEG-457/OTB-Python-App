"""Streaming controller for managing live data viewing."""

from PyQt5 import QtCore
from app.core.config import Config


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
        print("[STREAMING] start_streaming() called")
        self.is_streaming = True
        self.is_paused = False
        
        if self.receiver_thread is not None:
            # Start the receiver thread if not already running
            if not self.receiver_thread.isRunning():
                print("[STREAMING] Starting receiver thread...")
                self.receiver_thread.running = True
                self.receiver_thread.start()  # Actually start the QThread
                print("[STREAMING] Receiver thread started")
            else:
                print("[STREAMING] Receiver thread already running, setting running=True")
                self.receiver_thread.running = True
        else:
            print("[STREAMING] ERROR: receiver_thread is None!")
            
        self.timer.start(Config.UPDATE_RATE)  # Start timer with configured update rate
        self.status_update.emit("Streaming...")
        print(f"[STREAMING] Timer started with {Config.UPDATE_RATE}ms interval")
        return True
    
    def stop_streaming(self):
        """Stop live streaming."""
        print("[STREAMING] stop_streaming() called")
        self.is_streaming = False
        self.is_paused = True
        self.timer.stop()
        
        if self.receiver_thread is not None:
            print("[STREAMING] Stopping receiver thread...")
            self.receiver_thread.running = False
            # Give thread time to finish current iteration
            self.receiver_thread.wait(1000)  # Wait up to 1 second
            print("[STREAMING] Receiver thread stopped")
        
        self.status_update.emit("Stream stopped")
        print("[STREAMING] Live streaming stopped")
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
