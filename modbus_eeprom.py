# modbus_eeprom.py

import time
import json
from modbus_registers import PRESET_GROUPS, BLOCKED_GROUPS, DANGEROUS_REGISTERS, PRESET_UNITS_DEVICE_CLASSES
from console_info import print_presets_table

def build_safe_preset_registers():
    """Flatten and return preset registers excluding blocked/dangerous groups and registers."""
    safe_registers = {}
    for group_name, regs in PRESET_GROUPS.items():
        if group_name in BLOCKED_GROUPS:
            continue
        for key, reg in regs.items():
            if key in DANGEROUS_REGISTERS:
                continue
            safe_registers[key] = reg
    return safe_registers

def get_unit_and_device_class(label: str):
    label_lower = label.lower()
    for keyword, (unit, dev_class) in PRESET_UNITS_DEVICE_CLASSES.items():
        if keyword in label_lower:
            return unit, dev_class
    # Defaults
    return None, None

def format_value_and_unit(key, value):
    """Format the value and unit based on key prefix and keywords."""
    unit, device_class = get_unit_and_device_class(key)
    key_lower = key.lower()
    
    # Apply mV to V conversion ONLY if key starts with "pack_ov_" or "pack_uv_"
    # AND label doesn't contain 'time' or 'delay'
    if (key_lower.startswith("pack_ov_") or key_lower.startswith("pack_uv_")) and not ("time" in key_lower or "delay" in key_lower):
        volts = value / 100.0
        unit = "V"  # Override unit to volts
        return volts, unit, device_class  # <-- Return float, NOT formatted string
    
    # Otherwise, return the raw value as is
    return value, unit, device_class

def publish_mqtt_delete(client, label_keys):
    """Delete MQTT preset entities by publishing empty retained config topics."""
    base = "homeassistant/sensor/ritar_ess"
    for key in label_keys:
        key_clean = key.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("%", "pct")
        topic = f"{base}/x_{key_clean}/config"
        client.publish(topic, "", retain=True)

def publish_presets_in_ritar_device(client, preset: dict):
    base = "homeassistant/sensor/ritar_ess"
    device_info = {
        'identifiers': ['ritar_ess'],
        'name': 'Ritar ESS',
        'model': 'Energy Storage System',
        'manufacturer': 'Ritar'
    }

    def pub(suffix, name, value):
        formatted_value, unit, device_class = format_value_and_unit(name, value)
    
        cfg_topic = f"{base}/x_{suffix}/config"
        state_topic = f"{base}/x_{suffix}"
    
        cfg = {
            'name': f"x_{name}",
            'state_topic': state_topic,
            'unique_id': f"ritar_ess_{suffix}",
            'object_id': f"ritar_ess_{suffix}",
            'device': device_info,
            'value_template': '{{ value_json.state }}',
        }
    
        if unit:
            cfg['unit_of_measurement'] = unit
        if device_class:
            cfg['device_class'] = device_class
    
        client.publish(cfg_topic, json.dumps(cfg), retain=True)
        client.publish(state_topic, json.dumps({'state': formatted_value}), retain=True)  # numeric value!

    for label, value in preset.items():
        if value is None:
            continue
        key = label.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("%", "pct")
        pub(key, label, value)

def read_and_process_presets(client, gateway, battery_ids):
    preset_registers = build_safe_preset_registers()
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
