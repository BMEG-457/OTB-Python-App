import socket
import sys


class SessantaquattroPlus:
    def __init__(self, host="0.0.0.0", port=45454):
        self.host = host
        self.port = port
        self.nchannels = 72
        self.frequency = 2000
        self.server_socket = None
        self.client_socket = None

    def get_num_channels(self, NCH, MODE):
        if NCH == 0:
            return 12 if MODE == 1 else 16
        elif NCH == 1:
            return 16 if MODE == 1 else 24
        elif NCH == 2:
            return 24 if MODE == 1 else 40
        elif NCH == 3:
            return 40 if MODE == 1 else 72
        return 72

    def get_sampling_frequency(self, FSAMP, MODE):
        if MODE == 3:
            frequencies = {0: 2000, 1: 4000, 2: 8000, 3: 16000}
        else:
            frequencies = {0: 500, 1: 1000, 2: 2000, 3: 4000}
        return frequencies.get(FSAMP, 2000)

    def create_command(self, FSAMP=2, NCH=3, MODE=0, HRES=0, HPF=0, EXTEN=0, TRIG=0, REC=0, GO=1):
        self.nchannels = self.get_num_channels(NCH, MODE)
        self.frequency = self.get_sampling_frequency(FSAMP, MODE)

        Command = 0
        Command += GO
        Command += (REC << 1)
        Command += (TRIG << 2)
        Command += (EXTEN << 4)
        Command += (HPF << 6)
        Command += (HRES << 7)
        Command += (MODE << 8)
        Command += (NCH << 11)
        Command += (FSAMP << 13)

        print(format(Command, "016b"))
        return Command
    

    def is_connected_to_device_network(self, device_network_prefix="192.168.1"):
        """Check if connected to the device's WiFi network"""
        try:
            # Get the actual IP being used for network communication
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # Doesn't actually send data
            local_ip = s.getsockname()[0]
            s.close()
            
            print(f"Current IP: {local_ip}")
            
            if not local_ip.startswith(device_network_prefix):
                print(f"ERROR: Not connected to device network (expected {device_network_prefix}x)")
                return False
            
            return True
        except Exception as e:
            print(f"Error checking network: {e}")
            return False
        
    def start_server(self, connection_timeout=10):
        # Pre-flight checks
        if not self.is_connected_to_device_network():
            print("Please connect to the Sessantaquattroplus device's WiFi network first")
            sys.exit(1)
        
        command = self.create_command()
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Set a timeout for accept() to prevent indefinite hanging
            self.server_socket.settimeout(connection_timeout)
            
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            print(f"Listening on {self.host}:{self.port}...")
            print(f"Waiting for device connection (timeout: {connection_timeout}s)...")
            
            try:
                self.client_socket, addr = self.server_socket.accept()
                # Remove timeout for ongoing communication
                self.client_socket.settimeout(None)
                print(f"Connected to {addr}")
                
                self.client_socket.send(command.to_bytes(2, "big", signed=True))
                
            except socket.timeout:
                print(f"ERROR: Device did not connect within {connection_timeout} seconds")
                print("Make sure:")
                print("1. You're connected to the device's WiFi")
                print("2. The device is powered on and in pairing mode")
                print("3. No firewall is blocking the connection")
                self.server_socket.close()
                sys.exit(1)
                
        except socket.error as e:
            print(f"Server error: {e}")
            if self.server_socket:
                self.server_socket.close()
            sys.exit(1)

    def stop_server(self):
        if self.client_socket:
            self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()
