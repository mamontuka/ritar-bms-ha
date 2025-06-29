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
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack('<H', crc)

class ModbusGateway:
    def __init__(self, config):
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
            raise ValueError("Invalid connection_type; must be 'ethernet' or 'serial'")

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
            self._sock.close()
            self._sock = None
        if self._serial:
            self._serial.close()
            self._serial = None

    def send(self, data: bytes):
        if self.type == 'ethernet':
            self._sock.sendall(data)
        elif self.type == 'serial':
            self._serial.write(data)

    def recv(self, size: int) -> bytes:
        if self.type == 'ethernet':
            return self._sock.recv(size)
        elif self.type == 'serial':
            return self._serial.read(size)

    def read_registers(self, address, count=1):
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
            print("[ERROR] Unexpected function code")
            return None
        byte_count = response[2]
        data = response[3:3 + byte_count]
        return [int.from_bytes(data[i:i+2], 'big') for i in range(0, byte_count, 2)]

    def write_register(self, address, value):
        function_code = 0x10
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
            print("[ERROR] Unexpected function code")
            return False
        return True
