# mqtt_core.py

import json
import time
import sys
import importlib
import main_console

# --- Dynamic imports to support overrides like in main.py ---
custom_dir = "/config/united_bms"
if custom_dir not in sys.path:
    sys.path.insert(0, custom_dir)

modbus_registers = importlib.import_module("modbus_registers")
modbus_inverter = importlib.import_module("modbus_inverter")
main_settings = importlib.import_module("main_settings")
parser_temperature = importlib.import_module("parser_temperature")

# Extract constants and functions
INVERTER_PROTOCOLS = modbus_registers.INVERTER_PROTOCOLS
PRESET_UNITS_DEVICE_CLASSES = modbus_registers.PRESET_UNITS_DEVICE_CLASSES
INVERTER_PROTOCOLS_REVERSE = modbus_inverter.get_inverter_protocols_reverse(modbus_registers)


read_inverter_protocol = modbus_inverter.read_inverter_protocol
write_inverter_protocol = modbus_inverter.write_inverter_protocol
read_all_inverter_protocols = modbus_inverter.read_all_inverter_protocols

volt_min_limit = main_settings.volt_min_limit
volt_max_limit = main_settings.volt_max_limit
MANUFACTURER = main_settings.MANUFACTURER
BATTERY_BASE_TOPIC_TEMPLATE = main_settings.BATTERY_BASE_TOPIC_TEMPLATE
BATTERY_DEVICE_MODEL_TEMPLATE = main_settings.BATTERY_DEVICE_MODEL_TEMPLATE
BATTERY_DEVICE_IDENTIFIERS_TEMPLATE = main_settings.BATTERY_DEVICE_IDENTIFIERS_TEMPLATE
BATTERY_UNIQUE_ID_TEMPLATE = main_settings.BATTERY_UNIQUE_ID_TEMPLATE
BATTERY_OBJECT_ID_TEMPLATE = main_settings.BATTERY_OBJECT_ID_TEMPLATE
ESS_BASE_TOPIC = main_settings.ESS_BASE_TOPIC
ESS_DEVICE_IDENTIFIERS = main_settings.ESS_DEVICE_IDENTIFIERS
ESS_DEVICE_NAME = main_settings.ESS_DEVICE_NAME
ESS_DEVICE_MODEL = main_settings.ESS_DEVICE_MODEL
ESS_UNIQUE_ID_TEMPLATE = main_settings.ESS_UNIQUE_ID_TEMPLATE
ESS_OBJECT_ID_TEMPLATE = main_settings.ESS_OBJECT_ID_TEMPLATE
INVERTER_PROTOCOL_BASE_TOPIC = main_settings.INVERTER_PROTOCOL_BASE_TOPIC
INVERTER_PROTOCOL_UNIQUE_ID = main_settings.INVERTER_PROTOCOL_UNIQUE_ID
INVERTER_PROTOCOL_OBJECT_ID = main_settings.INVERTER_PROTOCOL_OBJECT_ID

filter_temperature_spikes = parser_temperature.filter_temperature_spikes

from main_arrays import (
    last_valid_voltage,
    last_valid_current,
    last_valid_power,
    last_valid_cycle_count,
    last_valid_temps,
    last_valid_extra,
)


# --- Helper to publish a single sensor config & state ---
def publish_sensor(client, cfg_topic, state_topic, cfg_dict, value):
    client.publish(cfg_topic, json.dumps(cfg_dict), retain=True)
    client.publish(state_topic, json.dumps({'state': value}), retain=True)


# --- Delete only battery cell MQTT topics when zero_pad_cells changes ---
def delete_battery_cell_topics_on_zeropad_change(client, num_batteries, zero_pad_cells, max_cells=16):
    """
    Publishes empty retained messages to delete cell topics that would change format
    if zero_pad_cells setting changes (e.g., cell_1 <-> cell_01).
    """
    for index in range(1, num_batteries + 1):
        base = BATTERY_BASE_TOPIC_TEMPLATE.format(index=index)
        for i in range(1, max_cells + 1):
            cell_id_padded = f"{i:02}"
            cell_id_unpadded = str(i)
            # If zero_pad_cells enabled, delete unpadded topics; else delete padded topics
            cell_id = cell_id_unpadded if zero_pad_cells else cell_id_padded

            client.publish(f"{base}/cell_{cell_id}/config", "", retain=True)
            client.publish(f"{base}/cell_{cell_id}", "", retain=True)


# --- Batteries MQTT sensors publisher ---
def publish_sensors(client, index, data, mos_temp, env_temp, model, zero_pad_cells=False):
    base = BATTERY_BASE_TOPIC_TEMPLATE.format(index=index)
    device_info = {
        'identifiers': [id_.format(index=index) for id_ in BATTERY_DEVICE_IDENTIFIERS_TEMPLATE],
        'name': BATTERY_DEVICE_MODEL_TEMPLATE.format(index=index),
        'model': model,
        'manufacturer': MANUFACTURER
    }

    def pub(suffix, name, dev_class, unit, value, state_class=None):
        cfg_topic = f"{base}/{suffix}/config"
        state_topic = f"{base}/{suffix}"
        cfg = {
            'name': name,
            'state_topic': state_topic,
            'unique_id': BATTERY_UNIQUE_ID_TEMPLATE.format(index=index, suffix=suffix),
            'object_id': BATTERY_OBJECT_ID_TEMPLATE.format(index=index, suffix=suffix),
            'device_class': dev_class,
            'unit_of_measurement': unit,
            'value_template': '{{ value_json.state }}',
            'device': device_info
        }
        if state_class:
            cfg['state_class'] = state_class

        publish_sensor(client, cfg_topic, state_topic, cfg, value)

    # Core sensors with caching fallback
    voltage = data['voltage']
    if voltage is not None and volt_min_limit <= voltage <= volt_max_limit:
        last_valid_voltage[index] = voltage
    elif index in last_valid_voltage:
        voltage = last_valid_voltage[index]

    current = data['current']
    if current is not None:
        last_valid_current[index] = current
    elif index in last_valid_current:
        current = last_valid_current[index]

    power = data['power']
    if power is not None:
        last_valid_power[index] = power
    elif index in last_valid_power:
        power = last_valid_power[index]

    pub('voltage', 'Voltage', 'voltage', 'V', voltage)
    pub('soc', 'SOC', 'battery', '%', data['soc'])
    pub('current', 'Current', 'current', 'A', current)
    pub('power', 'Power', 'power', 'W', power)

    cycle = data['cycle']
    if isinstance(cycle, int):
        last_valid_cycle_count[index] = cycle
        pub('cycle', 'Cycle Count', None, None, cycle, state_class='total_increasing')
    elif index in last_valid_cycle_count:
        pub('cycle', 'Cycle Count', None, None, last_valid_cycle_count[index], state_class='total_increasing')

    # Cell voltages
    if data['cells']:
        for i, v in enumerate(data['cells'], start=1):
            cell_id = f'{i:02}' if zero_pad_cells else str(i)
            pub(f'cell_{cell_id}', f'Cell {cell_id}', 'voltage', 'mV', v)

    # Temperatures with spike filtering and caching
    if data['temps']:
        last_temps = last_valid_temps.get(index, [])
        valid_temps = filter_temperature_spikes(
            data['temps'],
            last_temps,
            main_settings.temp_min_limit,
            main_settings.temp_max_limit,
            delta_limit=10
        )
        last_valid_temps[index] = valid_temps
        for i, t in enumerate(valid_temps, start=1):
            pub(f'temp_{i}', f'Temp {i}', 'temperature', '°C', t)

    last_mos, last_env = last_valid_extra.get(index, (None, None))

    def within_delta(new, old, limit=10):
        return old is None or abs(new - old) <= limit

    if mos_temp is not None and within_delta(mos_temp, last_mos):
        last_mos = mos_temp
        pub('temp_mos', 'T MOS', 'temperature', '°C', mos_temp)
    if env_temp is not None and within_delta(env_temp, last_env):
        last_env = env_temp
        pub('temp_env', 'T ENV', 'temperature', '°C', env_temp)

    last_valid_extra[index] = (last_mos, last_env)


# --- Summary Ritar ESS MQTT sensors publisher ---
def publish_summary_sensors(client, soc_avg, volt_avg, current_sum, power_sum, mos_avg=None, env_avg=None):
    base = ESS_BASE_TOPIC
    device_info = {
        'identifiers': ESS_DEVICE_IDENTIFIERS,
        'name': ESS_DEVICE_NAME,
        'model': ESS_DEVICE_MODEL,
        'manufacturer': MANUFACTURER
    }

    def pub(suffix, name, dev_class, unit, value, state_class=None):
        cfg_topic = f"{base}/{suffix}/config"
        state_topic = f"{base}/{suffix}"
        cfg = {
            'name': name,
            'state_topic': state_topic,
            'unique_id': ESS_UNIQUE_ID_TEMPLATE.format(suffix=suffix),
            'object_id': ESS_OBJECT_ID_TEMPLATE.format(suffix=suffix),
            'device_class': dev_class,
            'unit_of_measurement': unit,
            'value_template': '{{ value_json.state }}',
            'device': device_info
        }
        if state_class:
            cfg['state_class'] = state_class

        publish_sensor(client, cfg_topic, state_topic, cfg, value)

    if soc_avg is not None:
        pub('soc_avg', 'SOC Average', 'battery', '%', soc_avg, state_class='measurement')
    if volt_avg is not None:
        pub('voltage_avg', 'Voltage Average', 'voltage', 'V', float("{:.2f}".format(volt_avg)), state_class='measurement')
    if mos_avg is not None:
        pub('mos_avg', 'MOS Temp Average', 'temperature', '°C', round(mos_avg, 1), state_class='measurement')
    if env_avg is not None:
        pub('env_avg', 'ENV Temp Average', 'temperature', '°C', round(env_avg, 1), state_class='measurement')

    pub('current_total', 'Total Current', 'current', 'A', round(current_sum, 2), state_class='measurement')
    pub('power_total', 'Total Power', 'power', 'W', round(power_sum, 2), state_class='measurement')


# --- Batteries inverter protocol MQTT publisher ---
def publish_inverter_protocol(client, gateway, battery_ids, modbus_registers, on_write=None):
    base = INVERTER_PROTOCOL_BASE_TOPIC
    device_info = {
        'identifiers': ESS_DEVICE_IDENTIFIERS,
        'name': ESS_DEVICE_NAME,
        'model': ESS_DEVICE_MODEL,
        'manufacturer': MANUFACTURER
    }
    topic_cfg = f"{base}/config"
    topic_state = f"{base}/state"
    topic_cmd = f"{base}/set"

    cfg = {
        "name": "Inverter Protocol",
        "command_topic": topic_cmd,
        "state_topic": topic_state,
        "unique_id": INVERTER_PROTOCOL_UNIQUE_ID,
        "object_id": INVERTER_PROTOCOL_OBJECT_ID,
        "options": list(INVERTER_PROTOCOLS.values()),
        "value_template": "{{ value_json.state }}",
        "device": device_info
    }

    client.publish(topic_cfg, json.dumps(cfg), retain=True)

    types = []
    for bat in battery_ids:
        val = read_inverter_protocol(gateway, bat, modbus_registers)
        if val is not None:
            types.append(val)
        else:
            print(f"[WARN] No inverter protocol read from battery {bat}")
        time.sleep(0.5)

    if types:
        common = types[0]
        if all(t == common for t in types):
            client.publish(topic_state, json.dumps({"state": INVERTER_PROTOCOLS.get(common, "Unknown")}), retain=True)
        else:
            print("Mixed inverter protocols detected among batteries !!! SET INVERTER PROTOCOL IN MQTT **RITAR ESS** DEVICE !!!")
            client.publish(topic_state, json.dumps({"state": "Unknown"}), retain=True)
    else:
        print("[WARN] No inverter protocols read from any batteries")
        client.publish(topic_state, json.dumps({"state": "Unknown"}), retain=True)

    def on_message(client, userdata, msg):
        payload = msg.payload.decode().strip()
        value = INVERTER_PROTOCOLS_REVERSE.get(payload)
        if value is not None:
            print(f"[MQTT] Changing inverter protocol to: {payload} ({value})")
            if on_write:
                on_write()
            for bat in battery_ids:
                write_inverter_protocol(gateway, bat, value, modbus_registers, on_write=on_write)
                time.sleep(2)
            client.publish(topic_state, json.dumps({"state": payload}), retain=True)

            print("[INFO] Please wait result confirmation...")
            updated_protocols = read_all_inverter_protocols(client, gateway, battery_ids, modbus_registers)
            main_console.print_inverter_protocols_table_batteries(updated_protocols)
            print("[INFO] Next change available after 10 seconds !")
        else:
            print(f"[WARN] Unknown inverter protocol: {payload}")
        print("-" * 112)

    client.message_callback_add(topic_cmd, on_message)
    client.subscribe(topic_cmd)

    def refresh():
        types = []
        for bat in battery_ids:
            val = read_inverter_protocol(gateway, bat, modbus_registers)
            if val is not None:
                types.append(val)
            time.sleep(0.5)
        if types:
            common = types[0]
            if all(t == common for t in types):
                client.publish(topic_state, json.dumps({"state": INVERTER_PROTOCOLS.get(common, "Unknown")}), retain=True)
            else:
                client.publish(topic_state, json.dumps({"state": "Unknown"}), retain=True)
        else:
            client.publish(topic_state, json.dumps({"state": "Unknown"}), retain=True)

    return refresh


# --- BMS EEPROM format preset values into MQTT units/classes helpers ---
def format_value_and_unit(key, value):
    """Format the value and unit based on key prefix and keywords."""
    unit, device_class = get_unit_and_device_class(key)
    key_lower = key.lower()

    # Apply mV to V conversion ONLY if key starts with "pack_ov_" or "pack_uv_"
    # AND label doesn't contain 'time' or 'delay'
    if (key_lower.startswith("pack_ov_") or key_lower.startswith("pack_uv_") or key_lower == "pack_full_charge_voltage") \
            and not ("time" in key_lower or "delay" in key_lower):
        volts = value / 100.0
        unit = "V"  # Override unit to volts
        return volts, unit, device_class  # <-- Return float, NOT formatted string

    # Otherwise, return the raw value as is
    return value, unit, device_class


def get_unit_and_device_class(label: str):
    label_lower = label.lower()

    # Prevent device_class for specific preset key
    if label_lower.strip() == "soc_alarm_threshold":
        unit, _ = PRESET_UNITS_DEVICE_CLASSES.get("soc", ("%", "battery"))
        return unit, None  # Keep % unit but remove device_class

    for keyword, (unit, dev_class) in PRESET_UNITS_DEVICE_CLASSES.items():
        if keyword in label_lower:
            return unit, dev_class

    return None, None


# --- BMS EEPROM MQTT Delete values if batteries presets not match ---
def publish_mqtt_delete(client, label_keys):
    """Delete MQTT preset entities by publishing empty retained config topics."""
    base = ESS_BASE_TOPIC
    for key in label_keys:
        key_clean = key.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("%", "pct")
        topic = f"{base}/x_{key_clean}/config"
        client.publish(topic, "", retain=True)


# --- BMS EEPROM preset values MQTT Publisher ---
def publish_presets_in_ritar_device(client, preset: dict):
    base = ESS_BASE_TOPIC
    device_info = {
        'identifiers': ESS_DEVICE_IDENTIFIERS,
        'name': ESS_DEVICE_NAME,
        'model': ESS_DEVICE_MODEL,
        'manufacturer': MANUFACTURER
    }

    def pub(suffix, name, value):
        formatted_value, unit, device_class = format_value_and_unit(name, value)

        cfg_topic = f"{base}/x_{suffix}/config"
        state_topic = f"{base}/x_{suffix}"

        cfg = {
            'name': f"x_{name}",
            'state_topic': state_topic,
            'unique_id': ESS_UNIQUE_ID_TEMPLATE.format(suffix=f"x_{suffix}"),
            'object_id': ESS_OBJECT_ID_TEMPLATE.format(suffix=f"x_{suffix}"),
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
