# modbus_gateway.py
import socket
import serial
import struct
import time

def modbus_crc16(data: bytes) -> bytes:
    """
    Compute Modbus RTU CRC16 over the provided data.
    Returns CRC as two bytes (little-endian).
    """
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return struct.pack('<H', crc)

class ModbusGateway:
    """
    Unified Modbus Gateway for Ritar BMS systems.

    Supports:
    - TCP (RTU over Ethernet)
    - Serial (RTU over RS485/USB)
    """

    def __init__(self, config: dict):
        self._sock = None
        self._serial = None
        self.timeout = config.get('connection_timeout', 3)
        self.slave = config.get('slave', 1)
        self.type = config.get('connection_type')

        if self.type == 'ethernet':
            self.host = config['rs485gate_ip']
            self.port = config['rs485gate_port']
            self.mode = 'rtu_tcp'
        elif self.type == 'serial':
            self.serial_port = config['serial_port']
            self.baudrate = config.get('serial_baudrate', 9600)
            self.mode = 'rtu_serial'
        else:
            raise ValueError("Invalid connection_type: must be 'ethernet' or 'serial'")

    def open(self):
        """
        Open the communication channel (socket or serial).
        """
        if self.type == 'ethernet':
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self.timeout)
            self._sock.connect((self.host, self.port))
        elif self.type == 'serial':
            self._serial = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )

    def close(self):
        """
        Close any open connection.
        """
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    def send(self, data: bytes):
        """
        Send raw bytes to the gateway.
        """
        if self.type == 'ethernet':
            self._sock.sendall(data)
        elif self.type == 'serial':
            self._serial.write(data)

    def recv(self, size: int) -> bytes:
        """
        Receive raw bytes from the gateway.
        """
        if self.type == 'ethernet':
            return self._recv_all(size)
        elif self.type == 'serial':
            return self._serial.read(size)

    def _recv_all(self, size: int) -> bytes:
        """
        Helper to receive exactly 'size' bytes over TCP socket.
        """
        data = bytearray()
        while len(data) < size:
            chunk = self._sock.recv(size - len(data))
            if not chunk:
                break
            data.extend(chunk)
        return bytes(data)

    def read_registers(self, address: int, count: int = 1):
        """
        Optional: Read Modbus registers (Function 0x03).
        Not used with static binary queries but available for future extensions.
        """
        function_code = 0x03
        payload = struct.pack('>B B H H', self.slave, function_code, address, count)
        crc = modbus_crc16(payload)
        frame = payload + crc

        self.send(frame)
        time.sleep(0.1)

        expected_length = 5 + 2 * count
        response = self.recv(expected_length)

        if len(response) < expected_length:
            print("[ERROR] RTU response too short")
            return None
        if modbus_crc16(response[:-2]) != response[-2:]:
            print("[ERROR] CRC mismatch")
            return None
        if response[1] != function_code:
            print("[ERROR] Unexpected function code in response")
            return None

        byte_count = response[2]
        data = response[3:3 + byte_count]
        return [int.from_bytes(data[i:i+2], 'big') for i in range(0, byte_count, 2)]

    def write_register(self, address: int, value: int) -> bool:
        """
        Optional: Write to a Modbus register (Function 0x06).
        Not used in typical Ritar use case.
        """
        function_code = 0x06
        payload = struct.pack('>B B H H', self.slave, function_code, address, value)
        crc = modbus_crc16(payload)
        frame = payload + crc

        self.send(frame)
        time.sleep(0.1)

        response = self.recv(8)

        if len(response) < 8:
            print("[ERROR] RTU write response too short")
            return False
        if modbus_crc16(response[:-2]) != response[-2:]:
            print("[ERROR] CRC mismatch on write")
            return False
        if response[1] != function_code:
            print("[ERROR] Unexpected function code in write response")
            return False

        return True
