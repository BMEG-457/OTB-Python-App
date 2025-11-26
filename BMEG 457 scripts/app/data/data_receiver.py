import struct
import numpy as np
import time
from PyQt5 import QtCore
from app.processing.pipeline import ProcessingPipeline, get_pipeline


class DataReceiverThread(QtCore.QThread):
    data_received = QtCore.pyqtSignal(np.ndarray)
    # emits (stage_name, array) for intermediate outputs
    stage_output = QtCore.pyqtSignal(str, np.ndarray)
    status_update = QtCore.pyqtSignal(str)

    def __init__(self, device, client_socket, tracks):
        super().__init__()
        self.device = device
        self.client_socket = client_socket
        self.tracks = tracks
        self.running = False  # Changed: Start False, will be set True by streaming_controller
        self.packet_count = 0
        self.last_time = time.time()
        self.fps = 0
        # final pipeline used to produce the data fed to tracks
        # allow pre-configuration via app.processing.pipeline.get_pipeline('final')
        self.processor = get_pipeline('final')
        
        # Set socket timeout to prevent infinite blocking
        try:
            self.client_socket.settimeout(5.0)  # 5 second timeout
            print("[RECEIVER] Socket timeout set to 5 seconds")
        except Exception as e:
            print(f"[RECEIVER] WARNING: Could not set socket timeout: {e}")

    def run(self):
        # Calculate expected packet size - try frequency/16 first (standard)
        samples_per_packet_expected = self.device.frequency // 16
        packet_bytes_expected = self.device.nchannels * 2 * samples_per_packet_expected
        print(f"[RECEIVER] Thread run() started")
        print(f"[RECEIVER] Device config: {self.device.nchannels} channels at {self.device.frequency}Hz")
        print(f"[RECEIVER] Expected: {samples_per_packet_expected} samples/packet, {packet_bytes_expected} bytes/packet")
        print(f"[RECEIVER] Initial running state: {self.running}")

        # Actual packet size will be determined from first received packet
        packet_bytes = None
        first_packet = True

        # Keep thread alive indefinitely - only exit on error or explicit stop()
        thread_alive = True
        while thread_alive:
            try:
                # For first packet, receive with large buffer to detect actual size
                if first_packet:
                    data = self.client_socket.recv(65536)  # Large buffer to catch any size
                    if data:
                        packet_bytes = len(data)
                        samples_per_packet = packet_bytes // (self.device.nchannels * 2)
                        print(f"[RECEIVER] Auto-detected packet size: {packet_bytes} bytes ({samples_per_packet} samples/packet)")
                        first_packet = False
                else:
                    # Receive data with timeout handling
                    data = self.client_socket.recv(packet_bytes)
                
                if not data:
                    print("[RECEIVER] Socket closed by remote end")
                    thread_alive = False
                    break
                
                if len(data) != packet_bytes:
                    print(f"[RECEIVER] WARNING: Received {len(data)} bytes, expected {packet_bytes}")
                    # Try to receive remaining bytes
                    while len(data) < packet_bytes and self.running:
                        remaining = packet_bytes - len(data)
                        chunk = self.client_socket.recv(remaining)
                        if not chunk:
                            break
                        data += chunk
                    
                    if len(data) != packet_bytes:
                        print(f"[RECEIVER] ERROR: Incomplete packet ({len(data)}/{packet_bytes} bytes), skipping")
                        continue
                
                #shape packets to be fed to tracks
                unpacked = struct.unpack(f'>{len(data)//2}h', data)
                reshaped = np.array(unpacked).reshape((-1, self.device.nchannels)).T

                # Compute multiple pipeline outputs: raw, filtered, rectified, fft, final
                raw = reshaped
                try:
                    self.stage_output.emit('raw', raw.copy())
                except Exception as e:
                    print(f"[RECEIVER] ERROR emitting raw stage_output: {e}")

                # Try to run filtered pipeline, but fall back to raw if it fails
                try:
                    filtered = get_pipeline('filtered').run(raw)
                    try:
                        self.stage_output.emit('filtered', filtered.copy())
                    except Exception as e:
                        print(f"[RECEIVER] ERROR emitting filtered stage_output: {e}")
                except Exception as e:
                    # If filtering fails, use raw data
                    if self.packet_count == 1:
                        print(f"[RECEIVER] Filtering failed (likely small packet), using raw data: {e}")
                    filtered = raw

                # Try rectified pipeline
                try:
                    rectified = get_pipeline('rectified').run(filtered)
                    try:
                        self.stage_output.emit('rectified', rectified.copy())
                    except Exception as e:
                        print(f"[RECEIVER] ERROR emitting rectified stage_output: {e}")
                except Exception as e:
                    if self.packet_count == 1:
                        print(f"[RECEIVER] Rectification failed: {e}")
                    rectified = filtered

                # final processed data (fed to tracks) comes from the 'final' pipeline
                # If final pipeline fails, use rectified data
                try:
                    processed = self.processor.run(raw)
                except Exception as e:
                    if self.packet_count == 1:
                        print(f"[RECEIVER] Final processing failed, using rectified data: {e}")
                    processed = rectified

                try:
                    self.stage_output.emit('final', processed.copy())
                    if self.packet_count == 1:
                        print("[RECEIVER] First 'final' stage_output signal emitted")
                except Exception as e:
                    print(f"[RECEIVER] ERROR emitting final stage_output: {e}")

                # Only feed tracks and emit signals when streaming is active
                if self.running:
                    # feed tracks with the `processed` data (same layout as before)
                    idx = 0
                    for track in self.tracks:
                        track.feed(processed[idx:idx + track.num_channels])
                        idx += track.num_channels

                    self.data_received.emit(processed)

                self.packet_count += 1
                if self.packet_count == 1:
                    print(f"[RECEIVER] First packet received successfully! ({len(data)} bytes)")
                if self.packet_count % 100 == 0:
                    now = time.time()
                    elapsed = now - self.last_time
                    self.fps = 100 / elapsed if elapsed else 0
                    self.last_time = now
                    if self.running:  # Only emit status when streaming
                        self.status_update.emit(f"Data rate: {self.fps:.1f} packets/s")
                        print(f"[RECEIVER] Packet #{self.packet_count}: {self.fps:.1f} packets/s")

            except TimeoutError:
                # Socket timeout - this is normal when paused (running=False)
                if self.running:
                    print("[RECEIVER] Socket timeout while streaming - no data in 5 seconds")
                # Don't exit - just continue loop
                continue
            except Exception as e:
                print(f"[RECEIVER] Error: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                thread_alive = False
                break
        
        print(f"[RECEIVER] Thread run() exiting - total packets received: {self.packet_count}")

    def stop(self):
        """Completely stop the receiver thread (called on window close)."""
        print("[RECEIVER] stop() called - thread will exit on next iteration")
        self.running = False
        # Note: Thread will continue receiving but won't process until socket closes or timeout
