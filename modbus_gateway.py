# modbus_gateway.py

import socket
import serial
import struct
import time

def modbus_crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return struct.pack('<H', crc)

class ModbusGateway:
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
        if self.type == 'ethernet':
            self._sock.sendall(data)
        elif self.type == 'serial':
            self._serial.write(data)

    def recv(self, size: int) -> bytes:
        if self.type == 'ethernet':
            return self._recv_all(size)
        elif self.type == 'serial':
            return self._serial.read(size)

    def _recv_all(self, size: int) -> bytes:
        data = bytearray()
        deadline = time.time() + self.timeout
        while len(data) < size and time.time() < deadline:
            try:
                chunk = self._sock.recv(size - len(data))
            except socket.timeout:
                break
            if not chunk:
                break
            data.extend(chunk)
        return bytes(data)

    def _is_valid_response(self, response: bytes, expected_fc: int) -> bool:
        return (
            len(response) >= 5 and
            response[1] == expected_fc and
            modbus_crc16(response[:-2]) == response[-2:]
        )

    def read_registers(self, address: int, count: int = 1):
        function_code = 0x03
        payload = struct.pack('>B B H H', self.slave, function_code, address, count)
        crc = modbus_crc16(payload)
        frame = payload + crc

        self.send(frame)
        time.sleep(0.1)

        expected_length = 5 + 2 * count
        response = bytearray()
        deadline = time.time() + self.timeout
        while len(response) < expected_length and time.time() < deadline:
            chunk = self.recv(expected_length - len(response))
            if not chunk:
                break
            response.extend(chunk)

        if not self._is_valid_response(response, function_code):
            # print(f"[DEBUG] Invalid read response: {response.hex()}")
            print("[ERROR] Invalid Modbus read response")
            return None

        byte_count = response[2]
        data = response[3:3 + byte_count]
        return [int.from_bytes(data[i:i+2], 'big') for i in range(0, byte_count, 2)]

    def write_register(self, address: int, value: int) -> bool:
        function_code = 0x06
        payload = struct.pack('>B B H H', self.slave, function_code, address, value)
        crc = modbus_crc16(payload)
        frame = payload + crc

        self.send(frame)
        time.sleep(0.2)

        response = bytearray()
        deadline = time.time() + self.timeout
        while len(response) < 8 and time.time() < deadline:
            chunk = self.recv(8 - len(response))
            if not chunk:
                break
            response.extend(chunk)

        if not self._is_valid_response(response, function_code):
            # print(f"[DEBUG] Invalid write response: {response.hex()}")
            print("[ERROR] Invalid Modbus write response")
            return False

        return True
