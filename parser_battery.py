# parser_battery.py
# Battery telemetry parser with spike filtering and MQTT publishing
# This file handles:
# - Reading raw battery telemetry data via Modbus
# - Parsing voltage, current, SOC, cycle count, and power
# - Parsing individual cell voltages
# - Parsing temperature sensors including extra MOSFET and environmental temps
# - Filtering out spikes or invalid data
# - Caching last valid readings
# - Publishing all valid telemetry to MQTT broker

import time
import binascii
from statistics import median  # used in spike filtering

# Import temperature-related helper functions
from parser_temperature import (
    hex_to_temperature,         # Converts raw hex data to temperature list
    valid_len,                  # Checks if the received buffer length matches expectation
    process_extra_temperature,  # Handles extra temperature sensors like MOSFET and ENV
)

# MQTT publishing function
from mqtt_core import publish_sensors

# Import global caches and history for spike filtering
from main_arrays import (
    last_valid_voltage,     # Stores last valid voltage to recover from spikes
    last_valid_current,     # Stores last valid current
    last_valid_power,       # Stores last valid power
    last_valid_soc,         # Stores last valid state-of-charge
    last_valid_cycle_count, # Stores last valid cycle count
    last_n_voltages,        # Rolling history of voltages for spike filtering
    last_n_socs,            # Rolling history of SOCs for spike filtering
)

# Import configuration and helper functions
from main_helpers import filter_spikes, is_valid_number, get_num_cells_from_config

from main_settings import (
    BLOCK_BUF_LEN, CELLS_BUF_LEN, TEMP_BUF_LEN, EXTRA_TEMP_BUF_LEN, 
    MIN_VALID_CELLS,
    MAX_CURRENT_SPIKE, MAX_POWER_SPIKE, SPIKE_FILTER_KEYS, 
    CURRENT_SCALE, VOLTAGE_SCALE, SOC_SCALE, 
    OFFSET_CURRENT_START, OFFSET_CURRENT_END, OFFSET_VOLTAGE_START, OFFSET_VOLTAGE_END,
    OFFSET_SOC_START, OFFSET_SOC_END, OFFSET_CYCLE_START, OFFSET_CYCLE_END,
    NUM_CELLS, CELL_HEX_OFFSET, CELL_HEX_STEP, CELL_HEX_END,
    CONSOLE_SEPARATOR_LEN,
    SOC_MIN, SOC_MAX,
    RESULT_TEMPLATE, spike_filter_delta, delta_filter, history_len, TEMP_MQTT_LIMIT
)

# How many cells battery have 
DEFAULT_NUM_CELLS = NUM_CELLS
NUM_CELLS = get_num_cells_from_config(default=DEFAULT_NUM_CELLS)

# ==============================
# === Battery data parsing ===
# ==============================
def process_battery_data(index, block_buf, cells_buf, temp_buf,
                         cell_min_limit, cell_max_limit,
                         volt_min_limit, volt_max_limit,
                         temp_min_limit, temp_max_limit,
                         warnings_enabled=False):
    """
    Parse raw Modbus telemetry buffers from a single battery.
    - block_buf: core data (voltage, current, SOC, cycle, power)
    - cells_buf: individual cell voltages
    - temp_buf: temperatures
    Returns dictionary with parsed data, or None if core values invalid.
    """
    # Start with empty result
    result = RESULT_TEMPLATE.copy()

    # ------------------------------
    # Core telemetry parsing
    # ------------------------------
    if valid_len(block_buf, BLOCK_BUF_LEN):
        # Convert raw bytes to hex string for easier slicing
        hb = binascii.hexlify(block_buf).decode()

        # --- Current ---
        cur_raw = int(hb[OFFSET_CURRENT_START:OFFSET_CURRENT_END], 16)
        # Adjust for 2's complement negative numbers
        if cur_raw >= 0x8000:
            cur_raw -= 0x10000
        current = round(cur_raw / CURRENT_SCALE, 2)

        # --- Voltage ---
        voltage = round(int(hb[OFFSET_VOLTAGE_START:OFFSET_VOLTAGE_END], 16) / VOLTAGE_SCALE, 2)

        # --- SOC ---
        soc = round(int(hb[OFFSET_SOC_START:OFFSET_SOC_END], 16) / SOC_SCALE, 1)

        # --- Cycle count ---
        cycle = int(hb[OFFSET_CYCLE_START:OFFSET_CYCLE_END], 16)

        # --- Power calculation ---
        power = round(current * voltage, 2)

        # --- Validation ---
        if not (volt_min_limit <= voltage <= volt_max_limit):
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to invalid voltage: {voltage}")
            return None
        if not (SOC_MIN <= soc <= SOC_MAX):
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to invalid SOC: {soc}")
            return None
        if abs(current) > MAX_CURRENT_SPIKE:
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to current spike: {current}")
            return None
        if abs(power) > MAX_POWER_SPIKE:
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to power anomaly: {power}")
            return None

        # Store core telemetry
        result.update({
            'current': current,
            'voltage': voltage,
            'soc': soc,
            'cycle': cycle,
            'power': power
        })

    # ------------------------------
    # Cells parsing
    # ------------------------------
    if valid_len(cells_buf, CELLS_BUF_LEN) and cells_buf[0] == index:
        hv = binascii.hexlify(cells_buf).decode()
        raw_cells = [
            int(hv[CELL_HEX_OFFSET + CELL_HEX_STEP*i:CELL_HEX_END + CELL_HEX_STEP*i], 16)
            for i in range(NUM_CELLS)
        ]
        # Filter out out-of-bounds cells
        filtered = [v if cell_min_limit <= v <= cell_max_limit else None for v in raw_cells]
        # Only store if enough valid cells
        if len([v for v in filtered if v is not None]) >= MIN_VALID_CELLS:
            result['cells'] = filtered

    # ------------------------------
    # Temperature parsing
    # ------------------------------
    if valid_len(temp_buf, TEMP_BUF_LEN):
        hx = binascii.hexlify(temp_buf).decode()
        temps = hex_to_temperature(hx)
        # Keep only temperatures within limits
        result['temps'] = [t for t in temps if temp_min_limit <= t <= temp_max_limit]

    return result

# ==============================
# === Main battery handler ===
# ==============================
def handle_battery(
    client, index, queries, gateway, model, zero_pad_cells, queries_delay,
    cell_min_limit, cell_max_limit,
    volt_min_limit, volt_max_limit,
    temp_min_limit, temp_max_limit,
    warnings_enabled=False, console_output_enabled=False
):
    """
    High-level battery handler:
    - Executes Modbus queries safely
    - Parses raw telemetry
    - Applies spike filtering
    - Updates last valid caches
    - Publishes data to MQTT
    Returns MOSFET and ENV temperatures if available.
    """
    q = queries[index]

    # ------------------------------
    # Safe Modbus query wrapper
    # ------------------------------
    def safe_query(key, expected_len=None):
        """
        Sends a Modbus query and catches errors:
        - key: query name (e.g., 'get_block_voltage')
        - expected_len: number of bytes expected (optional)
        Returns response bytes or None if failed.
        """
        if key not in q:
            if warnings_enabled:
                print(f"[INFO] Battery {index} skipping missing query '{key}'")
            return None
        time.sleep(queries_delay)  # avoid flooding
        try:
            gateway.send(q[key])
            response = gateway.recv(expected_len) if expected_len else gateway.recv()
            return response
        except Exception as e:
            if warnings_enabled:
                print(f"[WARN] Battery {index} {key} read error: {e}")
            return None

    # ------------------------------
    # Query all Modbus data
    # ------------------------------
    bv = safe_query('get_block_voltage', BLOCK_BUF_LEN)
    cv = safe_query('get_cells_voltage', CELLS_BUF_LEN)
    tv = safe_query('get_temperature', TEMP_BUF_LEN)
    et = safe_query('get_extra_temperature', EXTRA_TEMP_BUF_LEN)

    # ------------------------------
    # Parse core telemetry
    # ------------------------------
    if bv is not None:
        data = process_battery_data(
            index, bv, cv, tv,
            cell_min_limit, cell_max_limit,
            volt_min_limit, volt_max_limit,
            temp_min_limit, temp_max_limit,
            warnings_enabled
        )
        if data is None:
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to invalid core data")
            return None
    else:
        # Fallback if main block unavailable: try parsing partial data
        data = RESULT_TEMPLATE.copy()
        if valid_len(cv, CELLS_BUF_LEN) and cv[0] == index:
            hv = binascii.hexlify(cv).decode()
            raw_cells = [
                int(hv[CELL_HEX_OFFSET + CELL_HEX_STEP*i:CELL_HEX_END + CELL_HEX_STEP*i], 16)
                for i in range(NUM_CELLS)
            ]
            filtered = [v if cell_min_limit <= v <= cell_max_limit else None for v in raw_cells]
            if len([v for v in filtered if v is not None]) >= MIN_VALID_CELLS:
                data['cells'] = filtered
        if tv is not None and valid_len(tv, TEMP_BUF_LEN):
            hx = binascii.hexlify(tv).decode()
            temps = hex_to_temperature(hx)
            data['temps'] = [t for t in temps if temp_min_limit <= t <= temp_max_limit]

    # ------------------------------
    # Extra temperature parsing (MOSFET/env)
    # ------------------------------
    mos_t, env_t = None, None
    if et:
        mos_t, env_t = process_extra_temperature(et, temp_min_limit, temp_max_limit)

    # ------------------------------
    # Spike filtering
    # ------------------------------
    # Voltage
    filtered_voltage = filter_spikes(data['voltage'], last_n_voltages[index], spike_filter_delta['voltage'])
    if filtered_voltage is not None:
        data['voltage'] = filtered_voltage
        last_n_voltages[index].append(filtered_voltage)
        if len(last_n_voltages[index]) > history_len:
            last_n_voltages[index].pop(0)

    # SOC
    filtered_soc = filter_spikes(data['soc'], last_n_socs[index], spike_filter_delta['soc'])
    if filtered_soc is not None:
        data['soc'] = filtered_soc
        last_n_socs[index].append(filtered_soc)
        if len(last_n_socs[index]) > history_len:
            last_n_socs[index].pop(0)

    # ------------------------------
    # Update last valid caches
    # ------------------------------
    if is_valid_number(data['voltage'], volt_min_limit, volt_max_limit):
        last_valid_voltage[index] = data['voltage']
    else:
        data['voltage'] = last_valid_voltage.get(index)

    if is_valid_number(data['current']):
        last_valid_current[index] = data['current']
    else:
        data['current'] = last_valid_current.get(index)

    if is_valid_number(data['power']):
        last_valid_power[index] = data['power']
    else:
        data['power'] = last_valid_power.get(index)

    if is_valid_number(data['soc'], 0, 100):
        last_valid_soc[index] = data['soc']
    else:
        data['soc'] = last_valid_soc.get(index)

    if isinstance(data['cycle'], int):
        last_valid_cycle_count[index] = data['cycle']
    else:
        data['cycle'] = last_valid_cycle_count.get(index)

    # ------------------------------
    # Console output
    # ------------------------------
    if console_output_enabled:
        print(f"Battery {index} SOC: {data['soc']} %, Voltage: {data['voltage']} V, "
              f"Cycles: {data['cycle']}, Current: {data['current']} A, Power: {data['power']} W")
        if data['cells']:
            print(f"Battery {index} Cells: {', '.join(str(v) for v in data['cells'])}")
        if data['temps']:
            print(f"Battery {index} Temps: {', '.join(str(t) for t in data['temps'])}°C")
        if mos_t is not None and env_t is not None:
            print(f"Battery {index} MOS Temp: {mos_t}°C, ENV Temp: {env_t}°C")
        print("-" * CONSOLE_SEPARATOR_LEN)

    # ------------------------------
    # Skip publishing if all core data invalid
    # ------------------------------
    if all(data[k] is None for k in ['voltage', 'soc', 'current', 'power', 'cycle']):
        if not (data['cells'] or data['temps'] or (mos_t is not None and env_t is not None)):
            if warnings_enabled:
                print(f"[WARN] Battery {index} has no valid data, skipping publish")
            return None

    # ------------------------------
    # Publish to MQTT
    # ------------------------------
    publish_sensors(client, index, data, mos_t, env_t, model, zero_pad_cells, temp_mqtt_limit=TEMP_MQTT_LIMIT)

    # Return extra temperatures for further processing if needed
    return mos_t, env_t
