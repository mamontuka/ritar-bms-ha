#!/usr/bin/env python3

# === Standard library imports ===
import os
import time
import sys
import paho.mqtt.client as mqtt  # MQTT client library

# === Local modules ===
import main_console                            # Console output utilities
ModbusGateway = None  # lazy import below      # Abstraction for Modbus communication gateway

# --- Main script entry point ---
if __name__ == '__main__':

    # --- Load config and basic helpers ---
    from main_helpers import (                 # Utility helpers
        load_config,
        validate_delay,
        has_zeropad_changed,
        save_zeropad_state,
        try_import_custom_module,
        get_optional_attr,
        process_battery
    )
    
    # Load the main configuration from options.json or fallback config.yaml
    config = load_config()
    connection_type = config.get("connection_type", "ethernet").lower()
    use_bluetooth = connection_type == "bluetooth"

    # Directory to load user override Python modules from (if any)
    custom_dir = "/config/united_bms"
    
    # Read user options for enabling optional features, default to True
    enable_modbus_inverter = config.get('enable_modbus_inverter', True)
    enable_modbus_eeprom = config.get('enable_modbus_eeprom', True)

    # Communication read timeout in seconds
    read_timeout = config.get('read_timeout', 15)

    # Dynamically load override modules if user provided custom versions
    main_settings = try_import_custom_module("main_settings", custom_dir)
    delta_filter = getattr(main_settings, "delta_filter", {})
    modbus_registers = try_import_custom_module("modbus_registers", custom_dir)
    modbus_battery = try_import_custom_module("modbus_battery", custom_dir)
    parser_battery = try_import_custom_module("parser_battery", custom_dir)
    parser_temperature = try_import_custom_module("parser_temperature", custom_dir)

    # BT connection
    bluetooth_bridge = None
    if use_bluetooth:
        try:
            bluetooth_gateway = try_import_custom_module("bluetooth_gateway", custom_dir)
            bluetooth_battery = try_import_custom_module("bluetooth_battery", custom_dir)
        except Exception:
            import bluetooth_gateway
            import bluetooth_battery

        bt_cmd_timeout = config.get("bluetooth_answer_wait_timeout", 2.0)
        bt_delay_between_query = config.get("bluetooth_delay_between_query", 0.5)
        bt_next_battery_delay = config.get("bluetooth_next_battery_delay", 3.0)
        
        num_bt_batteries = config.get("num_batteries", 1)

        # Estimate total time spent reading all batteries
        # For each battery: (max commands * per-command timeout + inter-command delays) + next battery delay
        # Here we approximate max commands = 5, adjust if needed or read from config
        max_commands_per_battery = 5
        estimated_bt_duration = num_bt_batteries * (max_commands_per_battery * bt_cmd_timeout + max_commands_per_battery * bt_delay_between_query)
        estimated_bt_duration += (num_bt_batteries - 1) * bt_next_battery_delay

        # Compute dynamic sleep time so that total cycle ≈ read_timeout
        dynamic_bt_sleep = max(0, read_timeout - estimated_bt_duration)
        print(f"[INFO] Dynamic Bluetooth sleep set to {dynamic_bt_sleep:.2f}s to fit read_timeout {read_timeout}s")
        
        # Build/resolve BT connection info from addon config first (preferred).
        # Config fields (from options.yaml) expected:
        #   bluetooth_gate_ip  - string IP
        #   bluetooth_gate_port - int port
        # We pass the whole config to BluetoothBridge and let it decide fallbacks.
        bluetooth_bridge = getattr(bluetooth_gateway, "BluetoothBridge")(config)
        # Print resolved URL for clarity; BluetoothBridge will internally decide final URL.
        try:
            resolved_url = bluetooth_bridge.gate_url
        except Exception:
            resolved_url = "unknown"
        print(f"[INFO] Bluetooth mode selected — will use {resolved_url} for reads")

        modbus_inverter = None
        modbus_eeprom = None
        gateway = None

    # Conditionally load optional modules based on config switches
    if not use_bluetooth and enable_modbus_inverter:
        modbus_inverter = try_import_custom_module("modbus_inverter", custom_dir)
    else:
        modbus_inverter = None

    if not use_bluetooth and enable_modbus_eeprom:
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

    # --- ensure we use per-battery history for filtering ---
    from collections import defaultdict

    # Override global lists with per-battery history (defaultdict)
    if not isinstance(last_n_socs, defaultdict):
        last_n_socs = defaultdict(list)
    if not isinstance(last_n_voltages, defaultdict):
        last_n_voltages = defaultdict(list)

    # Safely get optional functions from modules, they might be missing
    filter_spikes = get_optional_attr(parser_battery, "filter_spikes")
    handle_battery = get_optional_attr(parser_battery, "handle_battery")
    filter_temperature_spikes = get_optional_attr(parser_temperature, "filter_temperature_spikes")

    # Get path to persistent zero_pad_cells state file, or use fallback path
    pad_state_path = get_optional_attr(main_settings, "PAD_STATE_PATH") or "/tmp/zeropad_state"

    # === NOTE about Bluetooth vs Modbus initialization ===
    # If Bluetooth mode selected, do not instantiate and open the Modbus gateway.
    # Instead main loop will call bluetooth_bridge.read_battery(...) and publish results.
    # If Bluetooth not selected, we keep original behavior (instantiate Modbus gateway).
    if not use_bluetooth:
        # Instantiate the Modbus gateway interface with config and register definitions
        from modbus_gateway import ModbusGateway
        gateway = ModbusGateway(config, modbus_registers)
    else:
        gateway = None  # keep variable defined for rest of code to reference safely

    # Get battery model name from config or use default
    battery_model = config.get('battery_model', 'BAT-5KWH-51.2V')

    # Flag whether to pad cell numbers with zeros in MQTT topics
    zero_pad_cells = config.get('zero_pad_cells', False)

    # Validate and parse delay settings for queries and between batteries
    queries_delay, next_battery_delay = validate_delay(config)

    # Flags to enable console output and warnings
    console_output_enabled = config.get('console_output_enabled', False)
    warnings_enabled = config.get('warnings_enabled', False)

    # Read polling mode from config: "sequential" or "all_in_one", by default now "sequential"
    separate_battery_reading = config.get('separate_battery_reading', True)
    
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
    
    # Open connection to Modbus gateway device (only when not Bluetooth)
    if not use_bluetooth:
        try:
            gateway.open()
        except Exception as e:
            print(f"[ERROR] Cannot open gateway: {e}")
            sys.exit(1)

    # Ensure mandatory handle_battery function is loaded before continuing (unless Bluetooth-only)
    if not handle_battery and not use_bluetooth:
        print("[ERROR] handle_battery() function not available — cannot continue.")
        sys.exit(1)

    # Number of batteries to poll
    num_batteries = config.get('num_batteries', 1)

    # Prepare all queries for each battery according to register definitions (used only in Modbus/serial)
    queries = {}
    if not use_bluetooth:
        queries = {
            i: modbus_battery.get_all_queries_for_battery(i, modbus_registers)
            for i in range(1, num_batteries + 1)
        }

    battery_ids = list(range(1, num_batteries + 1))

    # Setup and publish inverter protocols if enabled and module present
    refresh_inverter_protocol = None
    if enable_modbus_inverter and modbus_inverter is not None and not use_bluetooth:
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
        if use_bluetooth:
            print("[INFO] modbus_inverter skipped in Bluetooth mode")
        else:
            print("[INFO] modbus_inverter disabled; skipping inverter protocols read")
        protocols_list = []

    # Read and process EEPROM presets on startup if enabled (only Modbus path)
    if enable_modbus_eeprom and not use_bluetooth:
        print("Please wait for BMS EEPROM reading...")
        modbus_eeprom.read_and_process_presets(client, gateway, battery_ids, modbus_registers)
    else:
        if use_bluetooth:
            print("[INFO] EEPROM presets read skipped in Bluetooth mode")
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
            if time.time() < pause_polling_until:
                time.sleep(0.1)
                continue

            if use_bluetooth:
                time.sleep(dynamic_bt_sleep)
            else:
                time.sleep(read_timeout)

            if use_bluetooth:
                sum_current = 0.0
                sum_power = 0.0
                valid_socs = []
                valid_voltages = []
                valid_env = []
                valid_mos = []

                for i in battery_ids:
                    try:
                        result = bluetooth_bridge.read_battery(i, console_output_enabled)
                    except Exception as e:
                        print(f"[WARN] Bluetooth read failed for battery {i}: {e}")
                        result = None

                    if not result:
                        continue

                    data_dict, mos_t, env_t = result

                    # --- PUBLISH SENSORS ---
                    from mqtt_core import publish_sensors
                    publish_sensors(client, i, data_dict, mos_t, env_t, battery_model, zero_pad_cells)

                    # --- FILTER & ACCUMULATE ---
                    # Apply the same filtering functions as for Modbus
                    cur, powr = process_battery(
                        i, mos_t, env_t, main_settings, history_len,
                        last_valid_soc, last_valid_voltage, last_valid_current, last_valid_power,
                        last_n_socs, last_n_voltages, last_n_env, last_n_mos,
                        delta_filter, filter_spikes, filter_temperature_spikes,
                        valid_socs, valid_voltages, valid_env, valid_mos
                    )

                    if cur is not None:
                        sum_current += cur
                    if powr is not None:
                        sum_power += powr

                    time.sleep(next_battery_delay)

                # --- PUBLISH AGGREGATED METRICS ---
                soc_avg = round(sum(valid_socs) / len(valid_socs), 1) if valid_socs else None
                volt_avg = round(sum(valid_voltages) / len(valid_voltages), 2) if valid_voltages else None
                mos_avg = round(sum(valid_mos) / len(valid_mos), 1) if len(valid_mos) >= num_batteries else None
                env_avg = round(sum(valid_env) / len(valid_env), 1) if len(valid_env) >= num_batteries else None

                publish_summary_sensors(client, soc_avg, volt_avg, sum_current, sum_power, mos_avg, env_avg)

                continue  # skip Modbus loop

        # ---  MODBUS LOOP BELOW ---
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

            # --- Poll each battery according to selected mode ---
            battery_range = range(1, num_batteries + 1)
            for i in battery_range:
                # Sequential polling: add delay between batteries if needed
                if not separate_battery_reading and i > 1:
                    time.sleep(next_battery_delay)

                # Read each battery
                mos_t, env_t = handle_battery(
                    client, i, queries, gateway, battery_model, zero_pad_cells, queries_delay,
                    main_settings.cell_min_limit, main_settings.cell_max_limit,
                    main_settings.volt_min_limit, main_settings.volt_max_limit,
                    main_settings.temp_min_limit, main_settings.temp_max_limit,
                    warnings_enabled=warnings_enabled,
                    console_output_enabled=console_output_enabled
                ) or (None, None)

                # Filter values and accumulate sums
                cur, powr = process_battery(
                    i, mos_t, env_t, main_settings, history_len,
                    last_valid_soc, last_valid_voltage, last_valid_current, last_valid_power,
                    last_n_socs, last_n_voltages, last_n_env, last_n_mos,
                    delta_filter, filter_spikes, filter_temperature_spikes,
                    valid_socs, valid_voltages, valid_env, valid_mos
                )
                if cur is not None:
                    sum_current += cur
                if powr is not None:
                    sum_power += powr

            # Calculate averages of filtered values or None if no data
            soc_avg = round(sum(valid_socs) / len(valid_socs), 1) if valid_socs else None
            volt_avg = round(sum(valid_voltages) / len(valid_voltages), 2) if valid_voltages else None
            mos_avg = round(sum(valid_mos) / len(valid_mos), 1) if len(valid_mos) >= num_batteries else None
            env_avg = round(sum(valid_env) / len(valid_env), 1) if len(valid_env) >= num_batteries else None

            # Publish aggregated battery metrics via MQTT
            publish_summary_sensors(client, soc_avg, volt_avg, sum_current, sum_power, mos_avg, env_avg)

    except Exception as e:
        print(f"[ERROR] Exception in main loop: {e}")
    finally:
        # Clean up MQTT client loop and close gateway on exit
        client.loop_stop()
        if gateway:
            gateway.close()
