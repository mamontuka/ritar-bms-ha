# modbus_inverter.py

import time
import main_console

def get_inverter_protocols_reverse(modbus_registers):
    return {v: k for k, v in modbus_registers.INVERTER_PROTOCOLS.items()}

def read_inverter_protocol(gateway, battery_id, modbus_registers):
    regs = gateway.read_holding_registers(battery_id, modbus_registers.REG_INVERTER_PROTOCOL, 1)
    if regs:
        return regs[0]
    return None

def write_inverter_protocol(gateway, battery_id, value, modbus_registers, on_write=None):
    success = gateway.write_multiple_registers(battery_id, modbus_registers.REG_INVERTER_PROTOCOL, [value])
    if success and on_write:
        on_write()
    return success

def read_all_inverter_protocols(client, gateway, battery_ids, modbus_registers):
    results = []
    for bat in battery_ids:
        val = read_inverter_protocol(gateway, bat, modbus_registers)
        protocol = modbus_registers.INVERTER_PROTOCOLS.get(val, "Unknown") if val is not None else "No protocol read"
        results.append((bat, val, protocol))
        time.sleep(0.5)
    return results
