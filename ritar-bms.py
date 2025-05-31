#!/usr/bin/env python3

import time
import binascii
import os
import sys
import yaml
import json
import warnings
import paho.mqtt.client as mqtt
import protocol
from modbus_gateway import ModbusGateway

warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- Static limits ---
cell_min_limit = 2450
cell_max_limit = 4750
volt_min_limit = 40.00
volt_max_limit = 60.00
temp_min_limit = -20
temp_max_limit = 55

# Store last valid cycle counts
last_valid_cycle_count = {}

# Store last valid temperatures
last_valid_temps = {}
last_valid_extra = {}

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
    # Block voltage
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
        result.update({'current': current, 'voltage': voltage, 'soc': soc, 'cycle': cycle, 'power': power})
    # Cells voltage
    if valid_len(cells_buf, 37) and cells_buf[0] == index:
        hv = binascii.hexlify(cells_buf).decode()
        raw_cells = [int(hv[6 + 4*i:10 + 4*i], 16) for i in range(16)]
        filtered = [v if cell_min_limit <= v <= cell_max_limit else None for v in raw_cells]
        if len([v for v in filtered if v is not None]) >= 8:
            result['cells'] = filtered
    # Temperature buffer
    if valid_len(temp_buf, 13):
        hx = binascii.hexlify(temp_buf).decode()
        temps = hex_to_temperature(hx)
        result['temps'] = [t for t in temps if temp_min_limit <= t <= temp_max_limit]
    return result

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
    # Core sensors
    pub('voltage', 'Voltage', 'voltage', 'V', data['voltage'])
    pub('soc', 'SOC', 'battery', '%', data['soc'])
    pub('current', 'Current', 'current', 'A', data['current'])
    pub('power', 'Power', 'power', 'W', data['power'])
    # Cycle count
    cycle = data['cycle']
    if isinstance(cycle, int):
        last_valid_cycle_count[index] = cycle
        pub('cycle', 'Cycle Count', None, None, cycle, state_class='total_increasing')
    elif index in last_valid_cycle_count:
        pub('cycle', 'Cycle Count', None, None, last_valid_cycle_count[index], state_class='total_increasing')
    # Cell voltages
    for i, v in enumerate(data['cells'], start=1):
        cell_id = f'{i:02}' if zero_pad_cells else str(i)
        pub(f'cell_{cell_id}', f'Cell {cell_id}', 'voltage', 'mV', v)
    # Temperatures
    if data['temps']:
        last_temps = last_valid_temps.get(index, [])
        valid_temps = filter_temperature_spikes(data['temps'], last_temps)
        last_valid_temps[index] = valid_temps
        for i, t in enumerate(valid_temps, start=1):
            pub(f'temp_{i}', f'Temp {i}', 'temperature', '°C', t)
    # Extra temperatures
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

# --- Main execution ---
if __name__ == '__main__':
    config = load_config()
    gateway = ModbusGateway(config)
    battery_model = config.get('battery_model', 'BAT-5KWH-51.2V')
    read_timeout = config.get('read_timeout', 15)
    zero_pad_cells = config.get('zero_pad_cells', False)
    queries_delay, next_battery_delay = validate_delay(config)

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
    print(f"Connection Type: {gateway.type.title()}")
    if gateway.type == 'ethernet':
        print(f"  IP   : {config['rs485gate_ip']}")
        print(f"  Port : {config['rs485gate_port']}")
    else:
        print(f"  Device: {config['serial_port']}")
        print(f"  Baud  : {config.get('serial_baudrate', 9600)}")
    print(f"Read Timeout    : {read_timeout}s")
    print(f"Queries Delay   : {queries_delay}s")
    print(f"Next Bat. Delay : {next_battery_delay}s")
    print(f"Zero Pad Cells: {zero_pad_cells}")
    print("-" * 112)

    num_batt = config.get('num_batteries', 1)
    queries = {
        i: {
            'block_voltage': getattr(protocol, f'bat_{i}_get_block_voltage'),
            'cells_voltage': getattr(protocol, f'bat_{i}_get_cells_voltage'),
            'temperature': getattr(protocol, f'bat_{i}_get_temperature'),
            'extra_temperature': getattr(protocol, f'bat_{i}_get_extra_temperature')
        }
        for i in range(1, num_batt + 1)
    }

    # Main loop
    while True:
        time.sleep(read_timeout)
        try:
            gateway.open()
            for i in range(1, num_batt + 1):
                if i > 1:
                    time.sleep(next_battery_delay)
                q = queries[i]
                # Block voltage
                time.sleep(queries_delay)
                gateway.send(q['block_voltage'])
                bv = gateway.recv(37)
                if not valid_len(bv, 37):
                    bv = None
                # Cells voltage
                time.sleep(queries_delay)
                gateway.send(q['cells_voltage'])
                cv = gateway.recv(37)
                if not valid_len(cv, 37):
                    cv = None
                # Temperature
                time.sleep(queries_delay)
                gateway.send(q['temperature'])
                tv = gateway.recv(13)
                if not valid_len(tv, 13):
                    tv = None
                # Extra temperature
                et = None
                if tv:
                    time.sleep(queries_delay)
                    gateway.send(q['extra_temperature'])
                    et = gateway.recv(25)
                    if not valid_len(et, 25):
                        et = None
                # Process
                data = process_battery_data(i, bv, cv, tv)
                mos_t, env_t = process_extra_temperature(et)
                # Filter invalid
                if data['voltage'] is None or not (volt_min_limit <= data['voltage'] <= volt_max_limit):
                    continue
                if data['soc'] is None or not (0 <= data['soc'] <= 100):
                    continue
                if data['current'] is None:
                    continue
                # Console output
                print(f"Battery {i} SOC: {data['voltage']} V, Charged: {data['soc']} %, Cycles: {data['cycle']}, Current: {data['current']} A, Power: {data['power']} W")
                if data['cells']:
                    print(f"Battery {i} Cells: {', '.join(str(v) for v in data['cells'])}")
                if data['temps']:
                    print(f"Battery {i} Temps: {', '.join(str(t) for t in data['temps'])}°C")
                if mos_t is not None and env_t is not None:
                    print(f"Battery {i} MOS Temp: {mos_t}°C, ENV Temp: {env_t}°C")
                print("-" * 112)
                # Publish
                publish_sensors(client, i, data, mos_t, env_t, battery_model, zero_pad_cells)
            gateway.close()
        except Exception as e:
            print("Error:", e)
            time.sleep(read_timeout)
