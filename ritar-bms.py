#!/usr/bin/env python3

# === Import required modules ===
import time
import sys
import json
import paho.mqtt.client as mqtt
import console_info
import modbus_battery
import modbus_inverter
from modbus_gateway import ModbusGateway
from modbus_eeprom import read_and_process_presets
from parser_battery import process_battery_data, filter_spikes
from mqtt_core import (
    publish_sensors, publish_summary_sensors,
    publish_inverter_protocol,
    publish_presets_in_ritar_device, publish_mqtt_delete
)
from constants import (
    load_config, volt_min_limit, volt_max_limit,
    last_valid_voltage, last_valid_current, last_valid_power,
    last_valid_soc, last_valid_cycle_count, last_valid_temps,
    last_valid_extra, last_n_socs, last_n_voltages,
    history_len, pause_polling_until, to_float, validate_delay
)
from parser_temperature import (
    process_extra_temperature,
    filter_temperature_spikes,
)

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
    console_info.print_inverter_protocols_table(modbus_inverter.INVERTER_PROTOCOLS)

    # Open gateway connection
    try:
        gateway.open()
    except Exception as e:
        print(f"[ERROR] Cannot open gateway: {e}")
        sys.exit(1)

    num_batteries = config.get('num_batteries', 1)
    queries = {
        i: modbus_battery.get_all_queries_for_battery(i)
        for i in range(1, num_batteries + 1)
    }

    # Inverter protocol
    battery_ids = list(range(1, num_batteries + 1))

    refresh_inverter_protocol = publish_inverter_protocol(
        client,
        gateway,
        battery_ids,
        on_write=lambda: globals().__setitem__('pause_polling_until', time.time() + 10)
    )

    # Read all inverter protocols using the new function
    protocols_list = modbus_inverter.read_all_inverter_protocols(client, gateway, battery_ids)

    # Print the protocols in a pretty table
    console_info.print_inverter_protocols_table_batteries(protocols_list)

    # Read and publish EEPROM presets once at startup
    print("Please wait for BMS EEPROM reading...")
    read_and_process_presets(client, gateway, battery_ids)
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
