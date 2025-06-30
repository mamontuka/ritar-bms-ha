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

# === Suppress deprecation warnings ===
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- Global pause flag ---
pause_polling_until = 0

# --- Static limits ---
cell_min_limit = 2450
cell_max_limit = 4750
volt_min_limit = 40.00
volt_max_limit = 60.00
temp_min_limit = -20
temp_max_limit = 55

# --- Persistent cache for fallback values ---
last_valid_cycle_count = {}
last_valid_temps = {}
last_valid_extra = {}
last_valid_soc = {}
last_valid_voltage = {}
last_valid_current = {}
last_valid_power = {}

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

def valid_len(buf, length):
    return buf is not None and len(buf) == length

# --- Temperature parsers ---
def hex_to_temperature(hex_str):
    pairs = [hex_str[i:i+2] for i in range(0, len(hex_str), 2)]
    data = pairs[3:-2]
    if len(data) % 2:
        data = data[:-1]
    temps = []
    for i in range(0, len(data), 2):
        raw = int(data[i] + data[i+1], 16)
        temps.append(round((raw - 726) * 0.1 + 22.6, 1))
    return temps

def process_extra_temperature(data):
    if not valid_len(data, 25):
        return None, None
    hx = binascii.hexlify(data).decode()
    mos_raw = int(hx[6:10], 16)
    env_raw = int(hx[10:14], 16)
    mos = round((mos_raw - 726) * 0.1 + 22.6, 1)
    env = round((env_raw - 726) * 0.1 + 22.6, 1)
    mos_valid = mos if temp_min_limit <= mos <= temp_max_limit else None
    env_valid = env if temp_min_limit <= env <= temp_max_limit else None
    return mos_valid, env_valid

def filter_temperature_spikes(new_vals, last_vals, delta_limit=10):
    """Filter temperature list values based on max delta compared to last good values."""
    filtered = []
    for i, val in enumerate(new_vals):
        if val is None or not (temp_min_limit <= val <= temp_max_limit):
            filtered.append(None)
        elif i < len(last_vals):
            if abs(val - last_vals[i]) > delta_limit:
                filtered.append(last_vals[i])  # reuse last known good value
            else:
                filtered.append(val)
        else:
            filtered.append(val)
    return filtered

# --- Battery data parser ---
def process_battery_data(index, block_buf, cells_buf, temp_buf):
    result = {
        'voltage': None,
        'soc': None,
        'cycle': None,
        'current': None,
        'power': None,
        'cells': None,
        'temps': None
    }

    if valid_len(block_buf, 37):
        hb = binascii.hexlify(block_buf).decode()
        cur_raw = int(hb[6:10], 16)
        if cur_raw >= 0x8000:
            cur_raw -= 0x10000
        current = round(cur_raw / 100, 2)
        voltage = round(int(hb[10:14], 16) / 100, 2)
        soc = round(int(hb[14:18], 16) / 10, 1)
        cycle = int(hb[34:38], 16)
        power = round(current * voltage, 2)

        # === hard skip rules ===
        if not (volt_min_limit <= voltage <= volt_max_limit):
            print(f"[WARN] Battery {index} skipped due to invalid voltage: {voltage}")
            return None
        if not (0 <= soc <= 100):
            print(f"[WARN] Battery {index} skipped due to invalid SOC: {soc}")
            return None
        if abs(current) > 150:
            print(f"[WARN] Battery {index} skipped due to current spike: {current}")
            return None
        if abs(power) > 8000:
            print(f"[WARN] Battery {index} skipped due to power anomaly: {power}")
            return None

        result.update({'current': current, 'voltage': voltage, 'soc': soc, 'cycle': cycle, 'power': power})
    else:
        return None

    # Cell voltages
    if valid_len(cells_buf, 37) and cells_buf[0] == index:
        hv = binascii.hexlify(cells_buf).decode()
        raw_cells = [int(hv[6 + 4*i:10 + 4*i], 16) for i in range(16)]
        filtered = [v if cell_min_limit <= v <= cell_max_limit else None for v in raw_cells]
        if len([v for v in filtered if v is not None]) >= 8:
            result['cells'] = filtered

    # Temperatures
    if valid_len(temp_buf, 13):
        hx = binascii.hexlify(temp_buf).decode()
        temps = hex_to_temperature(hx)
        result['temps'] = [t for t in temps if temp_min_limit <= t <= temp_max_limit]

    return result

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
        print(f"[WARN] Battery {index} block voltage read error: {e}")
        bv = None

    time.sleep(queries_delay)
    gateway.send(q['get_cells_voltage'])
    try:
        cv = gateway.recv(37)
    except Exception as e:
        print(f"[WARN] Battery {index} cell voltage read error: {e}")
        cv = None

    time.sleep(queries_delay)
    gateway.send(q['get_temperature'])
    try:
        tv = gateway.recv(13)
    except Exception as e:
        print(f"[WARN] Battery {index} temperature read error: {e}")
        tv = None

    et = None
    if tv:
        time.sleep(queries_delay)
        gateway.send(q['get_extra_temperature'])
        try:
            et = gateway.recv(25)
        except Exception as e:
            print(f"[WARN] Battery {index} extra temperature read error: {e}")
            et = None

    data = process_battery_data(index, bv, cv, tv)
    if data is None:
        if console_output_enabled:
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
    read_timeout = config.get('read_timeout', 10)
    zero_pad_cells = config.get('zero_pad_cells', False)
    queries_delay, next_battery_delay = validate_delay(config)
    console_output_enabled = config.get('console_output_enabled', False)
    
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

    print("\nRitar ESS .. Reading inverter protocol from each battery..")

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

            sum_soc = 0.0
            sum_voltage = 0.0
            sum_current = 0.0
            sum_power = 0.0
            sum_mos = 0.0
            sum_env = 0.0
            mos_count = 0
            env_count = 0

            for i in range(1, num_batteries + 1):
                if i > 1:
                    time.sleep(next_battery_delay)

                mos_t, env_t = handle_battery(client, i, queries, gateway, battery_model, zero_pad_cells, queries_delay) or (None, None)

                if i in last_valid_soc:
                    sum_soc += last_valid_soc[i]
                if i in last_valid_voltage:
                    sum_voltage += last_valid_voltage[i]
                if i in last_valid_current:
                    sum_current += last_valid_current[i]
                if i in last_valid_power:
                    sum_power += last_valid_power[i]
                if mos_t is not None:
                    sum_mos += mos_t
                    mos_count += 1
                if env_t is not None:
                    sum_env += env_t
                    env_count += 1

            soc_avg = round(sum_soc / num_batteries, 1) if num_batteries else None
            volt_avg = round(sum_voltage / num_batteries, 2) if num_batteries else None
            mos_avg = round(sum_mos / mos_count, 1) if mos_count else None
            env_avg = round(sum_env / env_count, 1) if env_count else None

            publish_summary_sensors(client, soc_avg, volt_avg, sum_current, sum_power, mos_avg, env_avg)

    except Exception as e:
        print(f"[ERROR] Exception in main loop: {e}")
    finally:
        gateway.close()
