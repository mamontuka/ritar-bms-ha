#!/usr/bin/env python3

# === Import required modules ===
import time
import binascii
import os
import sys
import yaml
import json
import warnings
import paho.mqtt.client as mqtt
import protocol
import inverter_protocol
import console_info
from modbus_gateway import ModbusGateway

# Import temperature utils and battery parser
from temperature_utils import (
    hex_to_temperature,
    process_extra_temperature,
    filter_temperature_spikes,
    temp_min_limit,
    temp_max_limit,
    valid_len
)
from battery_parser import process_battery_data

# === Suppress deprecation warnings ===
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- Global pause flag ---
pause_polling_until = 0

# --- Static limits for cells and voltages ---
cell_min_limit = 2450
cell_max_limit = 4750
volt_min_limit = 40.00
volt_max_limit = 60.00

# --- Persistent cache for fallback values ---
last_valid_cycle_count = {}
last_valid_temps = {}
last_valid_extra = {}
last_valid_soc = {}
last_valid_voltage = {}
last_valid_current = {}
last_valid_power = {}

# === Added: History buffers for smoothing averages ===
last_n_socs = []
last_n_voltages = []
history_len = 5  # number of last values to keep

# --- Configuration loader ---
def load_config():
    if os.path.exists('/data/options.json'):
        with open('/data/options.json') as f:
            cfg = json.load(f)
    elif os.path.exists('config.yaml'):
        with open('config.yaml') as f:
            y = yaml.load(f, Loader=yaml.FullLoader)
            cfg = y.get('options', {})
    else:
        sys.exit("Error: No config file found")
    if cfg.get('connection_type') not in ('ethernet', 'serial'):
        sys.exit("Error: connection_type must be 'ethernet' or 'serial'")
    return cfg

# --- Helpers ---
def to_float(value, name):
    if isinstance(value, str):
        value = value.replace(',', '.')
    try:
        return float(value)
    except ValueError:
        sys.exit(f"Error: {name} must be a number, got {value}")

def validate_delay(cfg):
    qd = to_float(cfg.get('queries_delay', '0.1'), 'queries_delay')
    nb = to_float(cfg.get('next_battery_delay', '0.5'), 'next_battery_delay')
    return qd, nb

# === Added: Spike filter helper function ===
def filter_spikes(new_value, last_values, max_delta):
    if new_value is None:
        return None
    if not last_values:
        return new_value
    last_avg = sum(last_values) / len(last_values)
    if abs(new_value - last_avg) > max_delta:
        # Spike detected: use last average to smooth spike
        return last_avg
    return new_value

# --- MQTT sensor publisher ---
def publish_sensors(client, index, data, mos_temp, env_temp, model, zero_pad_cells=False):
    base = f"homeassistant/sensor/ritar_{index}"
    device_info = {
        'identifiers': [f"ritar_{index}"],
        'name': f"Ritar Battery {index}",
        'model': model,
        'manufacturer': 'Ritar'
    }
    def pub(suffix, name, dev_class, unit, value, state_class=None):
        cfg_topic = f"{base}/{suffix}/config"
        state_topic = f"{base}/{suffix}"
        cfg = {
            'name': name,
            'state_topic': state_topic,
            'unique_id': f"ritar_{index}_{suffix}",
            'object_id': f"ritar_{index}_{suffix}",
            'device_class': dev_class,
            'unit_of_measurement': unit,
            'value_template': '{{ value_json.state }}',
            'device': device_info
        }
        if state_class:
            cfg['state_class'] = state_class
        client.publish(cfg_topic, json.dumps(cfg), retain=True)
        client.publish(state_topic, json.dumps({'state': value}), retain=True)

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
        valid_temps = filter_temperature_spikes(data['temps'], last_temps)
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

# --- Summary MQTT sensors publisher ---
def publish_summary_sensors(client, soc_avg, volt_avg, current_sum, power_sum, mos_avg=None, env_avg=None):
    base = "homeassistant/sensor/ritar_ess"
    device_info = {
        'identifiers': ['ritar_ess'],
        'name': 'Ritar ESS',
        'model': 'Energy Storage System',
        'manufacturer': 'Ritar'
    }
    def pub(suffix, name, dev_class, unit, value, state_class=None):
        cfg_topic = f"{base}/{suffix}/config"
        state_topic = f"{base}/{suffix}"
        cfg = {
            'name': name,
            'state_topic': state_topic,
            'unique_id': f"ritar_ess_{suffix}",
            'object_id': f"ritar_ess_{suffix}",
            'device_class': dev_class,
            'unit_of_measurement': unit,
            'value_template': '{{ value_json.state }}',
            'device': device_info
        }
        if state_class:
            cfg['state_class'] = state_class
        client.publish(cfg_topic, json.dumps(cfg), retain=True)
        client.publish(state_topic, json.dumps({'state': value}), retain=True)
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

# --- Per-battery scoped processing ---
def handle_battery(client, index, queries, gateway, model, zero_pad_cells, queries_delay):
    q = queries[index]

    time.sleep(queries_delay)
    gateway.send(q['get_block_voltage'])
    try:
        bv = gateway.recv(37)
    except Exception as e:
        if warnings_enabled:
            print(f"[WARN] Battery {index} block voltage read error: {e}")
        bv = None

    time.sleep(queries_delay)
    gateway.send(q['get_cells_voltage'])
    try:
        cv = gateway.recv(37)
    except Exception as e:
        if warnings_enabled:
            print(f"[WARN] Battery {index} cell voltage read error: {e}")
        cv = None

    time.sleep(queries_delay)
    gateway.send(q['get_temperature'])
    try:
        tv = gateway.recv(13)
    except Exception as e:
        if warnings_enabled:
            print(f"[WARN] Battery {index} temperature read error: {e}")
        tv = None

    et = None
    if tv:
        time.sleep(queries_delay)
        gateway.send(q['get_extra_temperature'])
        try:
            et = gateway.recv(25)
        except Exception as e:
            if warnings_enabled:
                print(f"[WARN] Battery {index} extra temperature read error: {e}")
            et = None

    data = process_battery_data(index, bv, cv, tv)
    if data is None:
        if console_output_enabled:
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to invalid data")
            print("-" * 112)
        return None

    mos_t, env_t = process_extra_temperature(et)

    last_valid_voltage[index] = data['voltage']
    last_valid_current[index] = data['current']
    last_valid_power[index] = data['power']

    if data['soc'] is not None and 0 <= data['soc'] <= 100:
        last_valid_soc[index] = data['soc']
    if isinstance(data['cycle'], int):
        last_valid_cycle_count[index] = data['cycle']

    if console_output_enabled:
        print(f"Battery {index} SOC: {data['soc']} %, Voltage: {data['voltage']} V, Cycles: {data['cycle']}, Current: {data['current']} A, Power: {data['power']} W")
        if data['cells']:
            print(f"Battery {index} Cells: {', '.join(str(v) for v in data['cells'])}")
        if data['temps']:
            print(f"Battery {index} Temps: {', '.join(str(t) for t in data['temps'])}°C")
        if mos_t is not None and env_t is not None:
            print(f"Battery {index} MOS Temp: {mos_t}°C, ENV Temp: {env_t}°C")
        print("-" * 112)

    publish_sensors(client, index, data, mos_t, env_t, model, zero_pad_cells)

    return mos_t, env_t

# --- Main execution ---
if __name__ == '__main__':
    config = load_config()
    gateway = ModbusGateway(config)
    battery_model = config.get('battery_model', 'BAT-5KWH-51.2V')
    read_timeout = config.get('read_timeout', 15)
    zero_pad_cells = config.get('zero_pad_cells', False)
    queries_delay, next_battery_delay = validate_delay(config)
    console_output_enabled = config.get('console_output_enabled', False)
    warnings_enabled = config.get('warnings_enabled', False)
    
    # MQTT setup
    client = mqtt.Client(client_id='ritar_bms', protocol=mqtt.MQTTv311)
    client.username_pw_set(
        config.get('mqtt_username', 'homeassistant'),
        config.get('mqtt_password', 'mqtt_password_here')
    )
    client.connect(
        config.get('mqtt_broker', 'core-mosquitto'),
        config.get('mqtt_port', 1883),
        60
    )
    client.on_disconnect = lambda c, u, rc: c.reconnect()
    client.loop_start()

    # Print configuration
    console_info.print_config_table(config)
    console_info.print_inverter_protocols_table(inverter_protocol.INVERTER_PROTOCOLS)

    # Open gateway connection
    try:
        gateway.open()
    except Exception as e:
        print(f"[ERROR] Cannot open gateway: {e}")
        sys.exit(1)

    num_batteries = config.get('num_batteries', 1)
    queries = {
        i: protocol.get_all_queries_for_battery(i)
        for i in range(1, num_batteries + 1)
    }

    # Inverter protocol
    battery_ids = list(range(1, num_batteries + 1))

    refresh_inverter_protocol = inverter_protocol.publish_inverter_protocol(
        client,
        gateway,
        battery_ids,
        on_write=lambda: globals().__setitem__('pause_polling_until', time.time() + 10)
    )

    # Read all inverter protocols using the new function
    protocols_list = inverter_protocol.read_all_inverter_protocols(client, gateway, battery_ids)

    # Print the protocols in a pretty table
    console_info.print_inverter_protocols_table_batteries(protocols_list)
    print("-" * 112)
    
    # Main loop
    try:
        while True:
            if time.time() < pause_polling_until:
                time.sleep(0.1)
                continue
            time.sleep(read_timeout)

            # === Reconnect workaround ===
            try:
                gateway.close()
                time.sleep(0.2)
                gateway.open()
            except Exception as e:
                print(f"[ERROR] Failed to reopen gateway: {e}")
                continue

            sum_current = 0.0
            sum_power = 0.0
            sum_mos = 0.0
            sum_env = 0.0
            mos_count = 0
            env_count = 0

            # === Use these for filtered values ===
            valid_socs = []
            valid_voltages = []

            for i in range(1, num_batteries + 1):
                if i > 1:
                    time.sleep(next_battery_delay)

                mos_t, env_t = handle_battery(client, i, queries, gateway, battery_model, zero_pad_cells, queries_delay) or (None, None)

                # === Filter SOC with max delta 5% ===
                if i in last_valid_soc:
                    filtered_soc = filter_spikes(last_valid_soc[i], last_n_socs, max_delta=5)
                    valid_socs.append(filtered_soc)
                    if len(last_n_socs) >= history_len:
                        last_n_socs.pop(0)
                    last_n_socs.append(filtered_soc)

                # === Filter Voltage with max delta 2.0V ===
                if i in last_valid_voltage:
                    filtered_voltage = filter_spikes(last_valid_voltage[i], last_n_voltages, max_delta=2.0)
                    valid_voltages.append(filtered_voltage)
                    if len(last_n_voltages) >= history_len:
                        last_n_voltages.pop(0)
                    last_n_voltages.append(filtered_voltage)

                # Accumulate sums for total current and power
                current = last_valid_current.get(i)
                power = last_valid_power.get(i)
                if current is not None:
                    sum_current += current
                if power is not None:
                    sum_power += power

                # Accumulate temperatures for averages
                if mos_t is not None:
                    sum_mos += mos_t
                    mos_count += 1
                if env_t is not None:
                    sum_env += env_t
                    env_count += 1

            # Compute averages
            soc_avg = round(sum(valid_socs) / len(valid_socs), 1) if valid_socs else None
            volt_avg = round(sum(valid_voltages) / len(valid_voltages), 2) if valid_voltages else None
            mos_avg = round(sum_mos / mos_count, 1) if mos_count > 0 else None
            env_avg = round(sum_env / env_count, 1) if env_count > 0 else None

            # Publish summary sensors
            publish_summary_sensors(client, soc_avg, volt_avg, sum_current, sum_power, mos_avg, env_avg)

    except Exception as e:
        print(f"[ERROR] Exception in main loop: {e}")
    finally:
        gateway.close()
