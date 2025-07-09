#!/usr/bin/env python3

# === Standard library imports ===
import os
import time
import sys
import paho.mqtt.client as mqtt  # MQTT client library

# === Local modules ===
import main_console                            # Console output utilities
from modbus_gateway import ModbusGateway       # Abstraction for Modbus communication gateway

# --- Main script entry point ---
if __name__ == '__main__':

    # --- Load config and basic helpers ---
    from main_helpers import (                 # Utility helpers
        load_config,
        validate_delay,
        has_zeropad_changed,
        save_zeropad_state,
        try_import_custom_module,
        get_optional_attr
    )
    
    # Load the main configuration from options.json or fallback config.yaml
    config = load_config()

    # Directory to load user override Python modules from (if any)
    custom_dir = "/config/united_bms"
    
    # Read user options for enabling optional features, default to True
    enable_modbus_inverter = config.get('enable_modbus_inverter', True)
    enable_modbus_eeprom = config.get('enable_modbus_eeprom', True)

    # Dynamically load override modules if user provided custom versions
    main_settings = try_import_custom_module("main_settings", custom_dir)
    modbus_registers = try_import_custom_module("modbus_registers", custom_dir)
    modbus_battery = try_import_custom_module("modbus_battery", custom_dir)
    parser_battery = try_import_custom_module("parser_battery", custom_dir)
    parser_temperature = try_import_custom_module("parser_temperature", custom_dir)

    # Conditionally load optional modules based on config switches
    if enable_modbus_inverter:
        modbus_inverter = try_import_custom_module("modbus_inverter", custom_dir)
    else:
        modbus_inverter = None

    if enable_modbus_eeprom:
        modbus_eeprom = try_import_custom_module("modbus_eeprom", custom_dir)
    else:
        modbus_eeprom = None

    # === Now import dependent modules ===
    from mqtt_core import (
        publish_summary_sensors,                        # Publish aggregated battery data to MQTT
        publish_inverter_protocol,                      # Publish inverter protocol info to MQTT
        delete_battery_cell_topics_on_zeropad_change    # Cleanup MQTT topics if zero padding setting changes
    )

    from main_arrays import (                           # Global state arrays and constants
        last_valid_voltage,
        last_valid_current,
        last_valid_power,
        last_valid_soc,
        last_n_socs,
        last_n_voltages,
        last_n_env,
        last_n_mos,
        history_len,
        pause_polling_until
    )
    
    # Safely get optional functions from modules, they might be missing
    filter_spikes = get_optional_attr(parser_battery, "filter_spikes")
    handle_battery = get_optional_attr(parser_battery, "handle_battery")
    filter_temperature_spikes = get_optional_attr(parser_temperature, "filter_temperature_spikes")

    # Get path to persistent zero_pad_cells state file, or use fallback path
    pad_state_path = get_optional_attr(main_settings, "PAD_STATE_PATH") or "/tmp/zeropad_state"

    # Instantiate the Modbus gateway interface with config and register definitions
    gateway = ModbusGateway(config, modbus_registers)

    # Get battery model name from config or use default
    battery_model = config.get('battery_model', 'BAT-5KWH-51.2V')

    # Communication read timeout in seconds
    read_timeout = config.get('read_timeout', 15)

    # Flag whether to pad cell numbers with zeros in MQTT topics
    zero_pad_cells = config.get('zero_pad_cells', False)

    # Validate and parse delay settings for queries and between batteries
    queries_delay, next_battery_delay = validate_delay(config)

    # Flags to enable console output and warnings
    console_output_enabled = config.get('console_output_enabled', False)
    warnings_enabled = config.get('warnings_enabled', False)
    
    # Setup MQTT client with credentials and connection parameters
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
    # Auto-reconnect callback on disconnect
    client.on_disconnect = lambda c, u, rc: c.reconnect()
    client.loop_start()

    # Print current config settings nicely to console
    main_console.print_config_table(config)
    
    # Open connection to Modbus gateway device
    try:
        gateway.open()
    except Exception as e:
        print(f"[ERROR] Cannot open gateway: {e}")
        sys.exit(1)

    # Ensure mandatory handle_battery function is loaded before continuing
    if not handle_battery:
        print("[ERROR] handle_battery() function not available — cannot continue.")
        sys.exit(1)

    # Number of batteries to poll
    num_batteries = config.get('num_batteries', 1)

    # Prepare all queries for each battery according to register definitions
    queries = {
        i: modbus_battery.get_all_queries_for_battery(i, modbus_registers)
        for i in range(1, num_batteries + 1)
    }

    battery_ids = list(range(1, num_batteries + 1))

    # Setup and publish inverter protocols if enabled and module present
    refresh_inverter_protocol = None
    if enable_modbus_inverter and modbus_inverter is not None:
        refresh_inverter_protocol = publish_inverter_protocol(
            client,
            gateway,
            battery_ids,
            modbus_registers,
            on_write=lambda: globals().__setitem__('pause_polling_until', time.time() + 10)
        )

        # Print known inverter protocols statically defined in registers file
        print("\n[INFO] Supported inverter protocols from modbus_registers:\n")
        main_console.print_inverter_protocols_table(modbus_registers.INVERTER_PROTOCOLS)

        # Read actual inverter protocols configured in each battery
        protocols_list = modbus_inverter.read_all_inverter_protocols(
            client, gateway, battery_ids, modbus_registers
        )

        # Print currently set inverter protocols per battery
        print("\n[INFO] Inverter protocols currently set in batteries:\n")
        main_console.print_inverter_protocols_table_batteries(protocols_list)
    else:
        print("[INFO] modbus_inverter disabled; skipping inverter protocols read")
        protocols_list = []

    # Read and process EEPROM presets on startup if enabled
    if enable_modbus_eeprom:
        print("Please wait for BMS EEPROM reading...")
        modbus_eeprom.read_and_process_presets(client, gateway, battery_ids, modbus_registers)
    else:
        print("[INFO] EEPROM presets read skipped due to configuration")

    # Sleep a little to let MQTT topics settle
    time.sleep(5)

    # If zero_pad_cells setting changed since last run, clean up old MQTT topics
    if has_zeropad_changed(zero_pad_cells, pad_state_path):
        print("[INFO] zero_pad_cells setting changed — cleaning old cell MQTT topics...")
        delete_battery_cell_topics_on_zeropad_change(client, num_batteries, zero_pad_cells)
        save_zeropad_state(zero_pad_cells, pad_state_path)

    # Print separator line
    print("-" * 112)
    
    # === Main polling loop ===
    try:
        while True:
            # Pause polling if instructed (e.g. after inverter protocol write)
            if time.time() < pause_polling_until:
                time.sleep(0.1)
                continue

            # Wait configured timeout before each full polling iteration
            time.sleep(read_timeout)

            # Reopen Modbus gateway connection as a workaround to keep it stable
            try:
                gateway.close()
                time.sleep(0.2)
                gateway.open()
            except Exception as e:
                print(f"[ERROR] Failed to reopen gateway: {e}")
                continue

            # Initialize accumulators for current and power sums
            sum_current = 0.0
            sum_power = 0.0

            # Lists to accumulate filtered valid values for SOC, voltages, temperatures
            valid_socs = []
            valid_voltages = []
            valid_env = []
            valid_mos = []

            # Poll each battery sequentially
            for i in range(1, num_batteries + 1):
                # Delay between battery polls to avoid gateway overload
                if i > 1:
                    time.sleep(next_battery_delay)

                # Query and parse battery data; returns MOS and environmental temperatures
                mos_t, env_t = handle_battery(
                    client, i, queries, gateway, battery_model, zero_pad_cells, queries_delay,
                    main_settings.cell_min_limit, main_settings.cell_max_limit,
                    main_settings.volt_min_limit, main_settings.volt_max_limit,
                    main_settings.temp_min_limit, main_settings.temp_max_limit,
                    warnings_enabled=warnings_enabled,
                    console_output_enabled=console_output_enabled
                ) or (None, None)

                # --- SOC spike filtering ---
                if filter_spikes and i in last_valid_soc:
                    filtered_soc = filter_spikes(last_valid_soc[i], last_n_socs, max_delta=5)
                    if filtered_soc is not None:
                        last_n_socs.append(filtered_soc)
                        if len(last_n_socs) > history_len:
                            last_n_socs.pop(0)
                        valid_socs.append(filtered_soc)

                # --- Voltage spike filtering ---
                if filter_spikes and i in last_valid_voltage:
                    filtered_voltage = filter_spikes(last_valid_voltage[i], last_n_voltages, max_delta=2.0)
                    if filtered_voltage is not None:
                        last_n_voltages.append(filtered_voltage)
                        if len(last_n_voltages) > history_len:
                            last_n_voltages.pop(0)
                        valid_voltages.append(filtered_voltage)

                # --- Accumulate current and power for summary ---
                current = last_valid_current.get(i)
                power = last_valid_power.get(i)
                if current is not None:
                    sum_current += current
                if power is not None:
                    sum_power += power

                # --- MOS temperature spike filtering ---
                if filter_temperature_spikes and mos_t is not None:
                    if i not in last_n_mos:
                        last_n_mos[i] = []
                    filtered_mos_list = filter_temperature_spikes(
                        [mos_t], last_n_mos[i],
                        main_settings.temp_min_limit, main_settings.temp_max_limit,
                        delta_limit=2.0
                    )
                    filtered_mos = filtered_mos_list[0]
                    if filtered_mos is not None:
                        last_n_mos[i].append(filtered_mos)
                        if len(last_n_mos[i]) > history_len:
                            last_n_mos[i].pop(0)
                        valid_mos.append(filtered_mos)

                # --- Environmental temperature spike filtering ---
                if filter_temperature_spikes and env_t is not None:
                    if i not in last_n_env:
                        last_n_env[i] = []
                    filtered_env_list = filter_temperature_spikes(
                        [env_t], last_n_env[i],
                        main_settings.temp_min_limit, main_settings.temp_max_limit,
                        delta_limit=2.0
                    )
                    filtered_env = filtered_env_list[0]
                    if filtered_env is not None:
                        last_n_env[i].append(filtered_env)
                        if len(last_n_env[i]) > history_len:
                            last_n_env[i].pop(0)
                        valid_env.append(filtered_env)

            # Calculate averages of filtered values or None if no data
            soc_avg = round(sum(valid_socs) / len(valid_socs), 1) if valid_socs else None
            volt_avg = round(sum(valid_voltages) / len(valid_voltages), 2) if valid_voltages else None
            mos_avg = round(sum(valid_mos) / len(valid_mos), 1) if len(valid_mos) >= num_batteries else None
            env_avg = round(sum(valid_env) / len(valid_env), 1) if len(valid_env) >= num_batteries else None

            # Optionally you could use median instead of average for robustness
            # from statistics import median
            # mos_avg = round(median(valid_mos), 1) if valid_mos else None
            # env_avg = round(median(valid_env), 1) if valid_env else None

            # Publish aggregated battery metrics via MQTT
            publish_summary_sensors(client, soc_avg, volt_avg, sum_current, sum_power, mos_avg, env_avg)

    except Exception as e:
        print(f"[ERROR] Exception in main loop: {e}")
    finally:
        # Clean up MQTT client loop and close gateway on exit
        client.loop_stop()
        gateway.close()
