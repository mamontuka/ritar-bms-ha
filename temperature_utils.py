# temperature_utils.py

import binascii

# --- Static limits for temperatures ---
temp_min_limit = -20
temp_max_limit = 55

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
