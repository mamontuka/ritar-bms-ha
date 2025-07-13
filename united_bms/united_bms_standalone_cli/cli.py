#!/usr/bin/env python3
import os
import importlib.util
import argparse
import yaml
from modbus_gateway import ModbusGateway

# Load custom or fallback modbus_registers
def load_modbus_registers():
    """
    Tries to load modbus_registers.py from current working directory (as a custom override).
    If not found, uses default inline fallback with standard function codes.
    """
    custom_path = os.path.join(os.getcwd(), "modbus_registers.py")

    # Ensure we are not just importing ourselves
    if os.path.exists(custom_path) and not os.path.samefile(custom_path, __file__):
        try:
            spec = importlib.util.spec_from_file_location("modbus_registers", custom_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            print("[INFO] Loaded custom modbus_registers.py")
            return mod
        except Exception as e:
            print(f"[WARN] Failed to load custom modbus_registers.py: {e}")
    
    # Default fallback
    #print("[INFO] Using internal default modbus_registers")
    class DefaultRegisters:
        FUNC_READ_HOLDING_REGS = 0x03
        FUNC_WRITE_SINGLE_REG = 0x06
        FUNC_WRITE_MULTIPLE_REGS = 0x10
    return DefaultRegisters()

modbus_registers = load_modbus_registers()

# Load YAML map and normalize keys to uppercase
def load_register_map(filename='register_map.yaml'):
    """
    Loads YAML register map (name -> address), and uppercases all keys for case-insensitive lookup.
    """
    try:
        with open(filename, 'r') as f:
            raw_map = yaml.safe_load(f)
            return {k.upper(): v for k, v in raw_map.items()}
    except FileNotFoundError:
        print(f"[WARN] Register map '{filename}' not found. Only numeric addresses will work.")
        return {}

# Helper to resolve named or numeric register
def resolve_register(reg_map, name_or_number):
    """
    Resolves register name or numeric string to integer address.
    """
    if isinstance(name_or_number, int):
        return name_or_number
    if name_or_number.isdigit():
        return int(name_or_number)
    key = name_or_number.upper()
    if key in reg_map:
        return reg_map[key]
    raise ValueError(f"Register '{name_or_number}' not found in map or is invalid.")

def read_register(gateway, address, count=1):
    result = gateway.read_holding_registers(gateway.slave, address, count)
    if result is None:
        print(f"[READ] Failed to read register {address}")
    else:
        print(f"[READ] Register {address} values:", result)

def write_register(gateway, address, value):
    success = gateway.write_register(gateway.slave, address, value)
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
    parser = argparse.ArgumentParser(description="United BMS debug tool")
    parser.add_argument('--tcp', help='TCP address like 192.168.0.100:50500')
    parser.add_argument('--serial', help='Serial port like /dev/ttyUSB0')
    parser.add_argument('--slave', type=int, default=1, help='Modbus slave ID (default: 1)')
    parser.add_argument('--read', help='Register name or address to read')
    parser.add_argument('--count', type=int, default=1, help='Number of registers to read (default: 1)')
    parser.add_argument('--write', type=parse_write_argument, help='ONLY AT YOUR OWN RISK! Format: <register=value>')
    parser.add_argument('--map', default='register_map.yaml', help='YAML file with register name -> address map')
    parser.add_argument('--mode', choices=['rtu_tcp', 'rtu_serial'], default='rtu_tcp',
                        help='Modbus connection mode: rtu_tcp (default), or rtu_serial')
    parser.add_argument('--timeout', type=int, default=3, help='Connection timeout in seconds (default: 3)')

    args = parser.parse_args()
    reg_map = load_register_map(args.map)

    # Assemble config dict for gateway
    if args.tcp:
        host, port = args.tcp.split(':')
        port = int(port)
        cfg = {
            'connection_type': 'ethernet',
            'rs485gate_ip': host,
            'rs485gate_port': port,
            'modbus_mode': args.mode,
            'slave': args.slave,
            'connection_timeout': args.timeout,
        }
    elif args.serial:
        cfg = {
            'connection_type': 'serial',
            'serial_port': args.serial,
            'serial_baudrate': 9600,
            'slave': args.slave,
            'connection_timeout': args.timeout,
        }
    else:
        print("❌ Please specify either --tcp or --serial. See --help for options.")
        return

    try:
        gateway = ModbusGateway(cfg, modbus_registers)
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
