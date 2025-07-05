# modbus_inverter.py

import time
import console_info

from modbus_registers import (
    REG_INVERTER_PROTOCOL,
    INVERTER_PROTOCOLS,
)

INVERTER_PROTOCOLS_REVERSE = {v: k for k, v in INVERTER_PROTOCOLS.items()}

def read_inverter_protocol(gateway, battery_id):
    regs = gateway.read_holding_registers(battery_id, REG_INVERTER_PROTOCOL, 1)
    if regs:
        return regs[0]
    return None

def write_inverter_protocol(gateway, battery_id, value, on_write=None):
    success = gateway.write_multiple_registers(battery_id, REG_INVERTER_PROTOCOL, [value])
    if success and on_write:
        on_write()
    return success

def read_all_inverter_protocols(client, gateway, battery_ids):
    results = []
    for bat in battery_ids:
        val = read_inverter_protocol(gateway, bat)
        results.append((bat, val, INVERTER_PROTOCOLS.get(val, "Unknown") if val is not None else "No protocol read"))
        time.sleep(0.5)
    return results
