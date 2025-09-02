# parser_temperature.py
# Temperature telemetry parser with spike filtering
# This file handles:
# - Converting raw temperature data from hex buffers to Celsius
# - Parsing MOSFET and ENV temperatures from extra buffer
# - Filtering out sudden spikes
# - Validating temperature values against min/max limits

import binascii
from statistics import median  # Used for robust spike filtering

from main_settings import (
    TEMP_HEADER_BYTES, TEMP_FOOTER_BYTES,
    TEMP_BYTE_STEP, TEMP_RAW_OFFSET,
    TEMP_SCALE, TEMP_BASE_OFFSET, TEMP_ROUND_DIGITS,
    EXTRA_TEMP_BUF_LEN,
    MOS_HEX_START, MOS_HEX_END,
    ENV_HEX_START, ENV_HEX_END,
    DELTA_TEMP_LIMIT
)

def valid_len(buf, length):
    """
    Check if the given buffer is not None and exactly matches the expected length.
    
    Args:
        buf (bytes): Input binary data buffer.
        length (int): Expected length in bytes.
    
    Returns:
        bool: True if buffer exists and length matches; False otherwise.
    """
    return buf is not None and len(buf) == length

def hex_to_temperature(hex_str):
    """
    Convert a hex string containing raw temperature sensor data into a list of temperatures.
    Uses main_settings constants for header/footer removal and conversion.
    
    Args:
        hex_str (str): Hexadecimal string representing raw temperature data.
    
    Returns:
        list of float: List of converted temperatures rounded to TEMP_ROUND_DIGITS.
    """
    # Split hex string into byte-sized pairs
    pairs = [hex_str[i:i+2] for i in range(0, len(hex_str), 2)]
    
    # Remove header and footer according to settings
    data = pairs[TEMP_HEADER_BYTES:-TEMP_FOOTER_BYTES]
    
    # Ensure even number of bytes for pairing
    if len(data) % 2:
        data = data[:-1]
    
    temps = []
    for i in range(0, len(data), TEMP_BYTE_STEP):
        # Combine two hex bytes into a single raw value
        raw = int(data[i] + data[i+1], 16)
        # Convert raw value to Celsius using constants
        temp_c = (raw - TEMP_RAW_OFFSET) * TEMP_SCALE + TEMP_BASE_OFFSET
        temps.append(round(temp_c, TEMP_ROUND_DIGITS))
    
    return temps

def process_extra_temperature(data, temp_min_limit, temp_max_limit):
    """
    Parse extra temperature data from a binary buffer and validate MOS and ENV temperatures.
    
    Args:
        data (bytes): Binary buffer containing raw temperature data (expected length: EXTRA_TEMP_BUF_LEN)
        temp_min_limit (float): Minimum valid temperature limit
        temp_max_limit (float): Maximum valid temperature limit
    
    Returns:
        tuple: (mos_valid, env_valid) each float or None if out of limits or buffer invalid
    """
    if not valid_len(data, EXTRA_TEMP_BUF_LEN):
        return None, None
    
    # Convert binary data to hex string for easier slicing
    hx = binascii.hexlify(data).decode()
    
    # Extract raw MOS and ENV values using settings constants
    mos_raw = int(hx[MOS_HEX_START:MOS_HEX_END], 16)
    env_raw = int(hx[ENV_HEX_START:ENV_HEX_END], 16)
    
    # Convert raw values to Celsius
    mos = round((mos_raw - TEMP_RAW_OFFSET) * TEMP_SCALE + TEMP_BASE_OFFSET, TEMP_ROUND_DIGITS)
    env = round((env_raw - TEMP_RAW_OFFSET) * TEMP_SCALE + TEMP_BASE_OFFSET, TEMP_ROUND_DIGITS)
    
    # Validate against limits
    mos_valid = mos if temp_min_limit <= mos <= temp_max_limit else None
    env_valid = env if temp_min_limit <= env <= temp_max_limit else None
    
    return mos_valid, env_valid

def filter_temperature_spikes(new_vals, last_vals, temp_min_limit, temp_max_limit, delta_limit=DELTA_TEMP_LIMIT):
    """
    Filter out sudden spikes in temperature readings by comparing with previous values.
    
    Args:
        new_vals (list of float/None): Latest temperature readings
        last_vals (list of float/None): Previous temperature readings for comparison
        temp_min_limit (float): Minimum valid temperature
        temp_max_limit (float): Maximum valid temperature
        delta_limit (float): Maximum allowed delta between consecutive readings
    
    Returns:
        list of float/None: Filtered temperature readings with spikes suppressed
    """
    filtered = []

    for i, val in enumerate(new_vals):
        # Reject invalid values immediately
        if val is None or not (temp_min_limit <= val <= temp_max_limit):
            filtered.append(None)
            continue

        if not last_vals:
            # No history, accept new value
            filtered.append(val)
            continue

        # Compute median of last valid values
        valid_history = [v for v in last_vals if v is not None]
        if not valid_history:
            filtered.append(val)
            continue

        median_val = median(valid_history)

        # Reject spike if difference exceeds delta_limit
        if abs(val - median_val) > delta_limit:
            filtered.append(last_vals[-1] if last_vals[-1] is not None else None)
        else:
            filtered.append(val)

    return filtered
