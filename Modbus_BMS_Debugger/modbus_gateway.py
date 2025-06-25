import socket
import serial
import struct
import time

def modbus_crc16(data: bytes) -> bytes:
    """Calculate Modbus RTU CRC16."""
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
    def __init__(self, cfg):
        """
        cfg dict must contain:
          - connection_mode: "modbus_tcp", "rtu_tcp", or "rtu_serial"
          - slave: Modbus slave ID (int)
          - For modbus_tcp and rtu_tcp:
            - host, port
            - timeout (optional)
          - For rtu_serial:
            - serial_port, baudrate, timeout (optional)
        """
        self.connection_mode = cfg['connection_mode']
        self.slave = cfg['slave']
        self.timeout = cfg.get('timeout', 3)

        if self.connection_mode in ('modbus_tcp', 'rtu_tcp'):
            self.host = cfg['host']
            self.port = cfg['port']
            self._sock = None
        elif self.connection_mode == 'rtu_serial':
            self.serial_port = cfg['serial_port']
            self.baudrate = cfg.get('baudrate', 9600)
            self._serial = None
        else:
            raise ValueError(f"Unknown connection_mode: {self.connection_mode}")

    def open(self):
        if self.connection_mode in ('modbus_tcp', 'rtu_tcp'):
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self.timeout)
            self._sock.connect((self.host, self.port))
        elif self.connection_mode == 'rtu_serial':
            self._serial = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )

    def close(self):
        if self.connection_mode in ('modbus_tcp', 'rtu_tcp') and self._sock:
            self._sock.close()
            self._sock = None
        elif self.connection_mode == 'rtu_serial' and self._serial:
            self._serial.close()
            self._serial = None

    def send(self, data: bytes):
        if self.connection_mode in ('modbus_tcp', 'rtu_tcp'):
            self._sock.sendall(data)
        elif self.connection_mode == 'rtu_serial':
            self._serial.write(data)

    def recv(self, size: int) -> bytes:
        if self.connection_mode in ('modbus_tcp', 'rtu_tcp'):
            return self._sock.recv(size)
        elif self.connection_mode == 'rtu_serial':
            return self._serial.read(size)

    def read_registers(self, address, count=1):
        function_code = 0x03

        if self.connection_mode == 'modbus_tcp':
            # Build Modbus TCP request
            trans_id = b'\x00\x01'          # Transaction ID
            proto_id = b'\x00\x00'          # Protocol ID
            length = struct.pack('>H', 6)  # Length of rest (UnitID + FC + addr + count)
            unit_id = struct.pack('B', self.slave)
            payload = struct.pack('>BHH', function_code, address, count)
            request = trans_id + proto_id + length + unit_id + payload

            self.send(request)
            response = self.recv(256)
            # Minimum response length: 9 bytes (TCP header + function + byte count + data)
            if len(response) < 9:
                print(f"[ERROR] Response too short: {len(response)} bytes")
                return None
            if response[1] != 0x03:
                print(f"[ERROR] Unexpected function code in response: {response[1]}")
                return None
            byte_count = response[2]
            data = response[3:3+byte_count]
            if len(data) < count*2:
                print(f"[ERROR] Data length less than expected: {len(data)} vs {count*2}")
                return None
            # Parse registers as big-endian unsigned shorts
            values = [int.from_bytes(data[i:i+2], 'big') for i in range(0, byte_count, 2)]
            return values

        elif self.connection_mode == 'rtu_tcp':
            # Build RTU frame (slave + FC + addr_hi + addr_lo + count_hi + count_lo + CRC16)
            payload = struct.pack('>B B H H', self.slave, function_code, address, count)
            crc = modbus_crc16(payload)
            frame = payload + crc

            self.send(frame)

            # RTU response minimal length: slave(1) + fc(1) + byte_count(1) + data(2*count) + crc(2)
            expected_length = 5 + 2 * count
            response = self.recv(expected_length)

            print(f"[DEBUG] Raw RTU TCP response: {response.hex()}")

            if len(response) < expected_length:
                print(f"[ERROR] Response too short: {len(response)} bytes, expected {expected_length}")
                return None

            # Validate CRC
            if modbus_crc16(response[:-2]) != response[-2:]:
                print("[ERROR] CRC check failed")
                return None

            if response[0] != self.slave:
                print(f"[ERROR] Response slave ID mismatch: got {response[0]}, expected {self.slave}")
                return None

            if response[1] & 0x80:
                print(f"[ERROR] Modbus exception response: code {response[2]}")
                return None

            if response[1] != function_code:
                print(f"[ERROR] Unexpected function code in response: {response[1]}")
                return None

            byte_count = response[2]
            data = response[3:3 + byte_count]
            values = [int.from_bytes(data[i:i + 2], 'big') for i in range(0, byte_count, 2)]
            return values

        elif self.connection_mode == 'rtu_serial':
            # RTU over serial, same as rtu_tcp frame
            payload = struct.pack('>B B H H', self.slave, function_code, address, count)
            crc = modbus_crc16(payload)
            frame = payload + crc

            self.send(frame)
            time.sleep(0.1)
            expected_length = 5 + 2 * count
            response = self.recv(expected_length)

            if len(response) < expected_length:
                print(f"[ERROR] Response too short: {len(response)} bytes, expected {expected_length}")
                return None

            if modbus_crc16(response[:-2]) != response[-2:]:
                print("[ERROR] CRC check failed")
                return None

            if response[0] != self.slave:
                print(f"[ERROR] Response slave ID mismatch: got {response[0]}, expected {self.slave}")
                return None

            if response[1] & 0x80:
                print(f"[ERROR] Modbus exception response: code {response[2]}")
                return None

            if response[1] != function_code:
                print(f"[ERROR] Unexpected function code in response: {response[1]}")
                return None

            byte_count = response[2]
            data = response[3:3 + byte_count]
            values = [int.from_bytes(data[i:i + 2], 'big') for i in range(0, byte_count, 2)]
            return values

        else:
            raise RuntimeError(f"Unsupported connection mode: {self.connection_mode}")

    def write_register(self, address, value):
        function_code = 0x06  # Write single register

        if self.connection_mode == 'modbus_tcp':
            trans_id = b'\x00\x02'
            proto_id = b'\x00\x00'
            length = struct.pack('>H', 6)
            unit_id = struct.pack('B', self.slave)
            payload = struct.pack('>BHH', function_code, address, value)
            request = trans_id + proto_id + length + unit_id + payload

            self.send(request)
            response = self.recv(256)

            if len(response) < 12:
                print(f"[ERROR] Response too short for write: {len(response)} bytes")
                return None

            if response[1] != function_code:
                print(f"[ERROR] Unexpected function code in write response: {response[1]}")
                return None

            # Simple success confirmation (echo of address and value)
            return True

        elif self.connection_mode in ('rtu_tcp', 'rtu_serial'):
            payload = struct.pack('>B B H H', self.slave, function_code, address, value)
            crc = modbus_crc16(payload)
            frame = payload + crc

            self.send(frame)

            # Response length: slave(1) + fc(1) + addr(2) + val(2) + crc(2)
            expected_length = 8
            response = self.recv(expected_length)

            print(f"[DEBUG] Raw RTU write response: {response.hex()}")

            if len(response) < expected_length:
                print(f"[ERROR] Response too short for write: {len(response)} bytes, expected {expected_length}")
                return None

            if modbus_crc16(response[:-2]) != response[-2:]:
                print("[ERROR] CRC check failed for write")
                return None

            if response[0] != self.slave:
                print(f"[ERROR] Response slave ID mismatch: got {response[0]}, expected {self.slave}")
                return None

            if response[1] & 0x80:
                print(f"[ERROR] Modbus exception response: code {response[2]}")
                return None

            if response[1] != function_code:
                print(f"[ERROR] Unexpected function code in write response: {response[1]}")
                return None

            # Success
            return True

        else:
            raise RuntimeError(f"Unsupported connection mode: {self.connection_mode}")
