# parser_battery.py

import time
import binascii

from statistics import median   # used in improved spike filter

from parser_temperature import (
    hex_to_temperature,         # Function to convert hex string to temperature values
    valid_len,                  # Helper to check if buffer length is valid
    process_extra_temperature,  # Function to process additional temperature info
)

from mqtt_core import publish_sensors  # Function to publish data to MQTT broker

from main_arrays import (
    last_valid_voltage,     # Lists to cache last valid readings for filtering spikes
    last_valid_current,
    last_valid_power,
    last_valid_soc,
    last_valid_cycle_count,
    last_n_voltages,
    last_n_socs,
)

from main_settings import spike_filter_delta, delta_filter
from main_helpers import filter_spikes, is_valid_number

# === Parse incoming battery data ===
def process_battery_data(index, block_buf, cells_buf, temp_buf,
                         cell_min_limit, cell_max_limit,
                         volt_min_limit, volt_max_limit,
                         temp_min_limit, temp_max_limit,
                         warnings_enabled=False):
    """
    Parse and validate battery telemetry from raw Modbus buffers:
    - block_buf: general data block including voltage, current, SOC, cycle count, power
    - cells_buf: individual cell voltages
    - temp_buf: temperatures

    Returns a dict with parsed and filtered data, or None if core data is invalid.
    """

    # Initialize result dictionary with None values for all expected battery metrics
    result = {
        'voltage': None,
        'soc': None,
        'cycle': None,
        'current': None,
        'power': None,
        'cells': None,
        'temps': None
    }

    # Check if the main data block buffer has the expected length (37 bytes)
    if valid_len(block_buf, 37):
        # Convert raw bytes to hex string for easier field extraction
        hb = binascii.hexlify(block_buf).decode()

        # Parse current (2 bytes), signed integer (16-bit, two's complement)
        cur_raw = int(hb[6:10], 16)
        if cur_raw >= 0x8000:  # Adjust negative values due to two's complement encoding
            cur_raw -= 0x10000
        current = round(cur_raw / 100, 2)  # Scale current to Amps with two decimals

        # Parse voltage (2 bytes), unsigned integer scaled by 100
        voltage = round(int(hb[10:14], 16) / 100, 2)

        # Parse SOC (state of charge) (2 bytes), scaled by 10
        soc = round(int(hb[14:18], 16) / 10, 1)

        # Parse cycle count (2 bytes), total charge/discharge cycles
        cycle = int(hb[34:38], 16)

        # Calculate power as voltage multiplied by current
        power = round(current * voltage, 2)

        # Validate values against configured static limits to filter out invalid/outlier data
        if not (volt_min_limit <= voltage <= volt_max_limit):
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to invalid voltage: {voltage} , its OK, casual Modbus lags")
            return None
        if not (0 <= soc <= 100):
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to invalid SOC: {soc}")
            return None
        if abs(current) > 150:  # Current spike filter threshold to catch unrealistic spikes
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to current spike: {current}")
            return None
        if abs(power) > 8000:  # Power anomaly filter threshold
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to power anomaly: {power}")
            return None

        # Update result dict with validated core telemetry data
        result.update({'current': current, 'voltage': voltage, 'soc': soc, 'cycle': cycle, 'power': power})

    else:
        # If block_buf is missing or invalid length,
        # do NOT return None immediately because partial data may still be processed
        # Continue with cells and temperature processing
        pass

    # Process cell voltages if buffer is valid and matches the battery index
    if valid_len(cells_buf, 37) and cells_buf[0] == index:
        hv = binascii.hexlify(cells_buf).decode()
        # Extract 16 cell voltages from buffer (each 2 bytes)
        raw_cells = [int(hv[6 + 4*i:10 + 4*i], 16) for i in range(16)]
        # Filter cell voltages: keep only values within valid range, else None
        filtered = [v if cell_min_limit <= v <= cell_max_limit else None for v in raw_cells]
        # Require at least 8 valid cells to consider the cell data trustworthy
        if len([v for v in filtered if v is not None]) >= 8:
            result['cells'] = filtered

    # Process temperature data if buffer length is valid
    if valid_len(temp_buf, 13):
        hx = binascii.hexlify(temp_buf).decode()
        temps = hex_to_temperature(hx)
        # Filter temperature readings to be within configured valid range
        result['temps'] = [t for t in temps if temp_min_limit <= t <= temp_max_limit]

    return result


# === Main Battery worker ===
def handle_battery(
    client, index, queries, gateway, model, zero_pad_cells, queries_delay,
    cell_min_limit, cell_max_limit,
    volt_min_limit, volt_max_limit,
    temp_min_limit, temp_max_limit,
    warnings_enabled=False, console_output_enabled=False
):
    """
    Main function to query a battery, parse and validate data, update caches, and publish MQTT sensors.

    Args:
        client: MQTT client instance.
        index: Battery index to query.
        queries: Dictionary of Modbus query byte arrays keyed by query name.
        gateway: Communication gateway object to send/receive Modbus data.
        model: Battery model string for MQTT device info.
        zero_pad_cells: Bool indicating if cell indexes in MQTT topics should be zero-padded.
        queries_delay: Delay in seconds between queries to prevent device overload.
        cell_min_limit, cell_max_limit: Valid voltage range for individual cells (mV).
        volt_min_limit, volt_max_limit: Valid voltage range for total battery voltage (V).
        temp_min_limit, temp_max_limit: Valid temperature range (°C).
        warnings_enabled: Enable printing warnings/info.
        console_output_enabled: Enable detailed console logging.

    Returns:
        Tuple of (mos_temperature, environment_temperature) if available, else (None, None).
        Returns None if data invalid or skipped.
    """

    q = queries[index]

    # Helper function to send Modbus queries safely and handle errors gracefully
    def safe_query(key, expected_len=None):
        """
        Sends a Modbus query safely with error handling.

        Args:
            key: Query name to send.
            expected_len: Expected response length in bytes for validation.

        Returns:
            Response bytes or None if query fails or missing.
        """
        if key not in q:
            if warnings_enabled:
                print(f"[INFO] Battery {index} skipping missing query '{key}'")
            return None
        time.sleep(queries_delay)  # Prevent flooding the device with requests
        try:
            gateway.send(q[key])
            response = gateway.recv(expected_len) if expected_len else gateway.recv()
            return response
        except Exception as e:
            if warnings_enabled:
                print(f"[WARN] Battery {index} {key} read error: {e}")
            return None

    # Perform all required Modbus queries safely and collect raw response data
    bv = safe_query('get_block_voltage', 37)      # Core battery telemetry data
    cv = safe_query('get_cells_voltage', 37)      # Individual cell voltages
    tv = safe_query('get_temperature', 13)        # Temperature sensors data
    et = safe_query('get_extra_temperature', 25)  # Extra temperature data (e.g., MOSFET and environment)

    # Parse and validate core battery data if block voltage buffer is valid
    if bv is not None:
        data = process_battery_data(index, bv, cv, tv,
                                    cell_min_limit, cell_max_limit,
                                    volt_min_limit, volt_max_limit,
                                    temp_min_limit, temp_max_limit,
                                    warnings_enabled)
        # If core data invalid, skip processing further to avoid bad data propagation
        if data is None:
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to invalid core data")
            return None
    else:
        # No core block data available, attempt partial parsing of cells and temperatures as fallback
        data = {
            'voltage': None,
            'soc': None,
            'cycle': None,
            'current': None,
            'power': None,
            'cells': None,
            'temps': None
        }
        # Process cells if valid buffer present
        if valid_len(cv, 37) and cv[0] == index:
            hv = binascii.hexlify(cv).decode()
            raw_cells = [int(hv[6 + 4*i:10 + 4*i], 16) for i in range(16)]
            filtered = [v if cell_min_limit <= v <= cell_max_limit else None for v in raw_cells]
            if len([v for v in filtered if v is not None]) >= 8:
                data['cells'] = filtered
        # Process temps if valid buffer present
        if tv is not None and valid_len(tv, 13):
            hx = binascii.hexlify(tv).decode()
            temps = hex_to_temperature(hx)
            data['temps'] = [t for t in temps if temp_min_limit <= t <= temp_max_limit]

    # Process additional temperature data such as MOSFET and environmental sensors
    mos_t, env_t = None, None
    if et:
        mos_t, env_t = process_extra_temperature(et, temp_min_limit, temp_max_limit)

    # Filter sudden spikes in voltage and SOC readings to reduce noise/artifacts
    max_delta_voltage = spike_filter_delta['voltage']
    max_delta_soc = spike_filter_delta['soc']

    filtered_voltage = filter_spikes(data['voltage'], last_n_voltages[index], max_delta_voltage)
    if filtered_voltage is not None:
        data['voltage'] = filtered_voltage
        last_n_voltages[index].append(filtered_voltage)
        if len(last_n_voltages[index]) > 10:
            last_n_voltages[index].pop(0)

    filtered_soc = filter_spikes(data['soc'], last_n_socs[index], max_delta_soc)
    if filtered_soc is not None:
        data['soc'] = filtered_soc
        last_n_socs[index].append(filtered_soc)
        if len(last_n_socs[index]) > 10:
            last_n_socs[index].pop(0)

    # Cache last valid voltage or fallback to previously cached value for stability
    if is_valid_number(data['voltage'], volt_min_limit, volt_max_limit):
        last_valid_voltage[index] = data['voltage']
    else:
        data['voltage'] = last_valid_voltage.get(index)

    # Cache last valid current similarly
    if is_valid_number(data['current']):
        last_valid_current[index] = data['current']
    else:
        data['current'] = last_valid_current.get(index)

    # Cache last valid power similarly
    if is_valid_number(data['power']):
        last_valid_power[index] = data['power']
    else:
        data['power'] = last_valid_power.get(index)

    # Cache last valid SOC or fallback
    if is_valid_number(data['soc'], 0, 100):
        last_valid_soc[index] = data['soc']
    else:
        data['soc'] = last_valid_soc.get(index)

    # Cache last valid cycle count if it is an integer, else fallback
    if isinstance(data['cycle'], int):
        last_valid_cycle_count[index] = data['cycle']
    else:
        data['cycle'] = last_valid_cycle_count.get(index)

    # Optional debug output to console with detailed battery telemetry
    if console_output_enabled:
        print(f"Battery {index} SOC: {data['soc']} %, Voltage: {data['voltage']} V, Cycles: {data['cycle']}, Current: {data['current']} A, Power: {data['power']} W")
        if data['cells']:
            print(f"Battery {index} Cells: {', '.join(str(v) for v in data['cells'])}")
        if data['temps']:
            print(f"Battery {index} Temps: {', '.join(str(t) for t in data['temps'])}°C")
        if mos_t is not None and env_t is not None:
            print(f"Battery {index} MOS Temp: {mos_t}°C, ENV Temp: {env_t}°C")
        print("-" * 112)

    # If no valid core data and no cells or temps, skip publishing to avoid empty MQTT updates
    if all(data[k] is None for k in ['voltage', 'soc', 'current', 'power', 'cycle']):
        if not (data['cells'] or data['temps'] or (mos_t is not None and env_t is not None)):
            if warnings_enabled:
                print(f"[WARN] Battery {index} has no valid data, skipping publish")
            return None

    # Publish all collected and filtered sensor data to MQTT broker
    publish_sensors(client, index, data, mos_t, env_t, model, zero_pad_cells)

    return mos_t, env_t
