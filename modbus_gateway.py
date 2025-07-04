# modbus_gateway.py

import socket
import serial
import struct
import time

from modbus_registers import FUNC_READ_HOLDING_REGS, FUNC_WRITE_SINGLE_REG, FUNC_WRITE_MULTIPLE_REGS

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
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self.timeout)
            self._sock.connect((self.host, self.port))
        elif self.type == 'serial':
            if self._serial and self._serial.is_open:
                try:
                    self._serial.close()
                except Exception:
                    pass
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

    def ensure_connected(self):
        """Check if connection is open; reopen if closed."""
        if self.type == 'ethernet':
            if not self._sock:
                print("[WARN] Socket not connected, reopening...")
                self.open()
        elif self.type == 'serial':
            if not self._serial or not self._serial.is_open:
                print("[WARN] Serial port not opened, reopening...")
                self.open()

    def send(self, data: bytes):
        self.ensure_connected()
        if self.type == 'ethernet':
            try:
                self._sock.sendall(data)
            except (socket.error, AttributeError) as e:
                print(f"[ERROR] Send failed: {e}, reconnecting...")
                self.open()
                self._sock.sendall(data)
        elif self.type == 'serial':
            try:
                self._serial.write(data)
            except (serial.SerialException, AttributeError) as e:
                print(f"[ERROR] Serial send failed: {e}, reopening...")
                self.open()
                self._serial.write(data)

    def recv(self, size: int) -> bytes:
        self.ensure_connected()
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
            except (socket.error, AttributeError) as e:
                print(f"[ERROR] Receive failed: {e}, reconnecting...")
                self.open()
                continue
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

    def read_holding_registers(self, slave: int, address: int, count: int = 1):
        function_code = FUNC_READ_HOLDING_REGS
        payload = struct.pack('>B B H H', slave, function_code, address, count)
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
            print("[ERROR] Invalid Modbus read response")
            return None

        byte_count = response[2]
        data = response[3:3 + byte_count]
        return [int.from_bytes(data[i:i+2], 'big') for i in range(0, byte_count, 2)]

    def write_register(self, slave: int, address: int, value: int) -> bool:
        function_code = FUNC_WRITE_SINGLE_REG
        payload = struct.pack('>B B H H', slave, function_code, address, value)
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

        if len(response) == 8:
            if response[:6] != payload:
                print(f"[WARN] Write response payload mismatch: {response.hex()} vs sent {payload.hex()}")
            if modbus_crc16(response[:-2]) != response[-2:]:
                print("[ERROR] Invalid CRC in Modbus write response")
                return False
        else:
            print(f"[ERROR] Unexpected Modbus write response length: {len(response)}, data: {response.hex()}")
            return False

        return True

    def write_multiple_registers(self, slave: int, address: int, values: list[int], max_retries=10, retry_delay=0.5) -> bool:
        count = len(values)
        byte_count = count * 2
        frame = bytearray()
        frame.append(slave)
        frame.append(FUNC_WRITE_MULTIPLE_REGS)
        frame += address.to_bytes(2, 'big')
        frame += count.to_bytes(2, 'big')
        frame.append(byte_count)
        for v in values:
            frame += v.to_bytes(2, 'big')
        crc = modbus_crc16(frame)
        frame += crc

        for attempt in range(1, max_retries + 1):
            try:
                self.send(bytes(frame))
            except Exception as e:
                print(f"[ERROR] Send failed on attempt {attempt}: {e}, reconnecting...")
                self.open()
                continue

            time.sleep(0.2)
            response = bytearray()
            deadline = time.time() + self.timeout
            while len(response) < 8 and time.time() < deadline:
                try:
                    chunk = self.recv(8 - len(response))
                except Exception as e:
                    print(f"[ERROR] Receive failed on attempt {attempt}: {e}, reconnecting...")
                    self.open()
                    break
                if not chunk:
                    break
                response.extend(chunk)
            if (len(response) == 8 and
                response[1] == FUNC_WRITE_MULTIPLE_REGS and
                modbus_crc16(response[:-2]) == response[-2:]):
                return True
            time.sleep(retry_delay)

        print(f"[ERROR] Write multiple registers failed after {max_retries} attempts")
        return False
    
