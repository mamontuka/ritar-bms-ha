#!/usr/bin/env python3
import argparse
import yaml
from modbus_gateway import ModbusGateway

def load_register_map(filename='register_map.yaml'):
    try:
        with open(filename, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"[WARN] Register map '{filename}' not found. Only numeric addresses will work.")
        return {}

def resolve_register(reg_map, name_or_number):
    if isinstance(name_or_number, int):
        return name_or_number
    if name_or_number.isdigit():
        return int(name_or_number)
    if name_or_number in reg_map:
        return reg_map[name_or_number]
    raise ValueError(f"Register '{name_or_number}' not found in map or is invalid.")

def read_register(gateway, address, count=1):
    result = gateway.read_registers(address, count)
    if result is None:
        print(f"[READ] Failed to read register {address}")
    else:
        print(f"[READ] Register {address} values:", result)

def write_register(gateway, address, value):
    success = gateway.write_register(address, value)
    if success:
        print(f"[WRITE] Register {address} set to {value}")
    else:
        print(f"[WRITE] Failed to write register {address}")

def parse_write_argument(arg: str):
    if '=' not in arg:
        raise argparse.ArgumentTypeError("Invalid --write format, expected <register=value>")
    reg, val = arg.split('=', 1)
    return reg.strip(), int(val.strip())

def main():
    parser = argparse.ArgumentParser(description="Unified Modbus BMS tool - https://github.com/mamontuka")
    parser.add_argument('--tcp', help='TCP address like 192.168.5.29:50500')
    parser.add_argument('--serial', help='Serial port like /dev/ttyUSB0')
    parser.add_argument('--slave', type=int, default=1, help='Modbus slave ID (default: 1)')
    parser.add_argument('--read', help='Register name or address to read')
    parser.add_argument('--count', type=int, default=1, help='Number of registers to read (default: 1)')
    parser.add_argument('--write', type=parse_write_argument, help='Write format: <register=value>')
    parser.add_argument('--map', default='register_map.yaml', help='YAML file with register name -> address map')
    parser.add_argument('--mode', choices=['modbus_tcp', 'rtu_tcp', 'rtu_serial'], default='rtu_tcp',
                        help='Modbus connection mode: modbus_tcp, rtu_tcp (default), or rtu_serial')
    parser.add_argument('--timeout', type=int, default=3, help='Connection timeout in seconds (default: 3)')

    args = parser.parse_args()
    reg_map = load_register_map(args.map)

    if args.tcp:
        host, port = args.tcp.split(':')
        port = int(port)
        cfg = {
            'connection_type': 'ethernet',
            'rs485gate_ip': host,
            'rs485gate_port': port,
            'modbus_mode': args.mode,
            'slave': args.slave,
            'timeout': args.timeout,
        }
    elif args.serial:
        cfg = {
            'connection_type': 'serial',
            'serial_port': args.serial,
            'serial_baudrate': 9600,
            'slave': args.slave,
            'timeout': args.timeout,
        }
    else:
        print("❌ Please specify either --tcp or --serial")
        return

    try:
        gateway = ModbusGateway(cfg)
        gateway.open()
    except Exception as e:
        print(f"[ERROR] Failed to open connection: {e}")
        return

    try:
        if args.read:
            try:
                reg_addr = resolve_register(reg_map, args.read)
            except ValueError as e:
                print(f"[ERROR] {e}")
                return
            read_register(gateway, reg_addr, args.count)

        if args.write:
            reg_name, value = args.write
            try:
                reg_addr = resolve_register(reg_map, reg_name)
            except ValueError as e:
                print(f"[ERROR] {e}")
                return
            write_register(gateway, reg_addr, value)

    finally:
        gateway.close()

if __name__ == "__main__":
    main()
