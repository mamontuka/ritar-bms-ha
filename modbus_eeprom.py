# modbus_eeprom.py

import time
from main_console import print_presets_table
from mqtt_core import publish_presets_in_ritar_device, publish_mqtt_delete

def build_safe_preset_registers(modbus_registers):
    """Flatten and return preset registers excluding blocked/dangerous groups and registers."""
    safe_registers = {}
    for group, regs in modbus_registers.PRESET_GROUPS.items():
        if group in modbus_registers.BLOCKED_GROUPS:
            continue
        for key, reg in regs.items():
            if key in modbus_registers.DANGEROUS_REGISTERS:
                continue
            safe_registers[key] = reg
    return safe_registers

def read_and_process_presets(client, gateway, battery_ids, modbus_registers):
    preset_registers = build_safe_preset_registers(modbus_registers)
    if not preset_registers:
        print("No safe preset registers to read.")
        return

    all_presets = {}

    for bat_id in battery_ids:
        preset_data = {}
        for label, register in preset_registers.items():
            try:
                # Directly call read_holding_registers with explicit slave ID
                values = gateway.read_holding_registers(bat_id, register, 1)
                preset_data[label] = values[0] if values else None
            except Exception as e:
                print(f"[ERROR] Reading preset '{label}' for battery {bat_id}: {e}")
                preset_data[label] = None
            time.sleep(0.05)
        all_presets[bat_id] = preset_data

    # Check if all values for each label match across all batteries
    all_labels = list(preset_registers.keys())
    presets_identical = True

    for label in all_labels:
        values = [all_presets[bat].get(label) for bat in battery_ids]
        if not all(v == values[0] and v is not None for v in values):
            presets_identical = False
            break

    if presets_identical:
        common_preset = {label: all_presets[battery_ids[0]][label] for label in all_labels}
        print("\n✅ All batteries have identical presets.\n")
        print_presets_table({0: common_preset})
        publish_presets_in_ritar_device(client, common_preset)
    else:
        print("\n⚠️ WARNING !!! PRESETS DIFFER BETWEEN BATTERIES!!! CHECK TABLES !!! ⚠️\n")
        print_presets_table(all_presets)
        label_keys = all_labels
        publish_mqtt_delete(client, label_keys)
