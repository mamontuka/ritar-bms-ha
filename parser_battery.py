# parser_battery.py

import binascii
from settings import cell_min_limit, cell_max_limit, volt_min_limit, volt_max_limit
from parser_temperature import (
    hex_to_temperature,
    temp_min_limit,
    temp_max_limit,
    valid_len,
)

# === Spike filter helper function ===
def filter_spikes(new_value, last_values, max_delta):
    if new_value is None:
        return None
    if not last_values:
        return new_value
    last_avg = sum(last_values) / len(last_values)
    if abs(new_value - last_avg) > max_delta:
        # Spike detected: use last average to smooth spike
        return last_avg
    return new_value

# === Registers parser ===
def process_battery_data(index, block_buf, cells_buf, temp_buf, warnings_enabled=False):
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

        # Hard skip rules
        if not (volt_min_limit <= voltage <= volt_max_limit):
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to invalid voltage: {voltage}")
            return None
        if not (0 <= soc <= 100):
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to invalid SOC: {soc}")
            return None
        if abs(current) > 150:
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to current spike: {current}")
            return None
        if abs(power) > 8000:
            if warnings_enabled:
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
