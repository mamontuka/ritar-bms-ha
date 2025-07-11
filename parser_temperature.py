# parser_temperature.py

import binascii

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
    
    The input hex string is expected to contain multiple temperature readings encoded in pairs of bytes.
    The function:
    - Splits the hex string into byte pairs.
    - Extracts the relevant subset of pairs (skipping some header and footer bytes).
    - Converts each temperature raw value from hex to integer.
    - Applies a linear transformation to convert the raw sensor value into degrees Celsius.
    
    Args:
        hex_str (str): Hexadecimal string representing raw temperature data.
    
    Returns:
        list of float: List of converted temperatures rounded to 1 decimal place.
    """
    # Split hex string into byte-sized pairs (2 chars each)
    pairs = [hex_str[i:i+2] for i in range(0, len(hex_str), 2)]
    
    # Remove header (first 3 pairs) and footer (last 2 pairs)
    data = pairs[3:-2]
    
    # If the data length is odd, remove the last byte to make pairs complete
    if len(data) % 2:
        data = data[:-1]
    
    temps = []
    # Process pairs two bytes at a time (each temperature uses 2 bytes)
    for i in range(0, len(data), 2):
        # Combine two hex byte strings into one raw hex number
        raw = int(data[i] + data[i+1], 16)
        # Convert raw sensor value to temperature using formula, round to 0.1 degree
        temps.append(round((raw - 726) * 0.1 + 22.6, 1))
    return temps

def process_extra_temperature(data, temp_min_limit, temp_max_limit):
    """
    Parse extra temperature data from a binary buffer and validate the MOS and ENV temperatures.
    
    The buffer should be exactly 25 bytes long.
    The MOS and ENV temperature raw values are extracted from specific byte offsets,
    converted to Celsius, and validated against min/max limits.
    
    Args:
        data (bytes): Binary buffer containing raw temperature data.
        temp_min_limit (float): Minimum valid temperature limit.
        temp_max_limit (float): Maximum valid temperature limit.
    
    Returns:
        tuple: (mos_valid, env_valid) where each is a float temperature or None if invalid.
    """
    # Validate buffer length
    if not valid_len(data, 25):
        return None, None
    
    # Convert binary data to hex string for easier slicing
    hx = binascii.hexlify(data).decode()
    
    # Extract raw MOS and ENV temperature hex strings (bytes 3-4 and 4-5)
    mos_raw = int(hx[6:10], 16)
    env_raw = int(hx[10:14], 16)
    
    # Convert raw values to temperature in Celsius using the known formula
    mos = round((mos_raw - 726) * 0.1 + 22.6, 1)
    env = round((env_raw - 726) * 0.1 + 22.6, 1)
    
    # Validate temperatures within acceptable limits, else assign None
    mos_valid = mos if temp_min_limit <= mos <= temp_max_limit else None
    env_valid = env if temp_min_limit <= env <= temp_max_limit else None
    
    return mos_valid, env_valid

def filter_temperature_spikes(new_vals, last_vals, temp_min_limit, temp_max_limit, delta_limit=1.0):
    """
    Filter out sudden spikes in temperature readings by comparing new values with previous ones.
    
    For each temperature value:
    - If value is None or out of specified min/max bounds, returns None.
    - If the difference between new and last value exceeds delta_limit, retains last stable value.
    - Otherwise, accepts new value.
    
    Args:
        new_vals (list of float or None): Latest temperature readings.
        last_vals (list of float or None): Previous temperature readings for comparison.
        temp_min_limit (float): Minimum valid temperature.
        temp_max_limit (float): Maximum valid temperature.
        delta_limit (float): Maximum allowed difference between consecutive readings.
    
    Returns:
        list of float or None: Filtered temperature readings with spikes suppressed.
    """
    filtered = []
    for i, val in enumerate(new_vals):
        # Reject if None or out of valid temperature range
        if val is None or not (temp_min_limit <= val <= temp_max_limit):
            filtered.append(None)
        # If last value exists and difference is too big, reject new value as spike
        elif i < len(last_vals):
            if abs(val - last_vals[i]) > delta_limit:
                filtered.append(last_vals[i])  # keep previous stable value
            else:
                filtered.append(val)  # accept new value
        else:
            # No previous value to compare, accept new
            filtered.append(val)
    return filtered
