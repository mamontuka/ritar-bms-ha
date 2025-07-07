# parser_battery.py

import time
import binascii

from main_settings import (
    cell_min_limit,
    cell_max_limit,
    volt_min_limit,
    volt_max_limit,
    temp_min_limit,
    temp_max_limit,
)

from parser_temperature import (
    hex_to_temperature,
    valid_len,
    process_extra_temperature,
)

from mqtt_core import publish_sensors

from main_arrays import (
    last_valid_voltage,
    last_valid_current,
    last_valid_power,
    last_valid_soc,
    last_valid_cycle_count,
)


# === Spike filter helper function ===
def filter_spikes(new_value, last_value, max_delta):
    if new_value is None:
        return None
    if last_value is None:
        return new_value
    if abs(new_value - last_value) > max_delta:
        return last_value  # smooth spike by holding previous
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

        # --- Hard Skip Rules ---
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

        # --- Spike Filtering ---
        voltage = filter_spikes(voltage, last_valid_voltage.get(index), max_delta=2.5)
        cycle = filter_spikes(cycle, last_valid_cycle_count.get(index), max_delta=50)

        # --- Update result ---
        result.update({
            'current': current,
            'voltage': voltage,
            'soc': soc,
            'cycle': cycle,
            'power': power
        })

    else:
        return None

    # --- Cell voltages ---
    if valid_len(cells_buf, 37) and cells_buf[0] == index:
        hv = binascii.hexlify(cells_buf).decode()
        raw_cells = [int(hv[6 + 4 * i:10 + 4 * i], 16) for i in range(16)]
        filtered = [v if cell_min_limit <= v <= cell_max_limit else None for v in raw_cells]
        if len([v for v in filtered if v is not None]) >= 8:
            result['cells'] = filtered

    # --- Temperatures ---
    if valid_len(temp_buf, 13):
        hx = binascii.hexlify(temp_buf).decode()
        temps = hex_to_temperature(hx)
        result['temps'] = [t for t in temps if temp_min_limit <= t <= temp_max_limit]

    return result


# === Per-battery scoped processing ===
def handle_battery(
    client, index, queries, gateway, model, zero_pad_cells, queries_delay,
    warnings_enabled=False, console_output_enabled=False
):
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

    data = process_battery_data(index, bv, cv, tv, warnings_enabled=warnings_enabled)
    if data is None:
        if console_output_enabled:
            if warnings_enabled:
                print(f"[WARN] Battery {index} skipped due to invalid data")
            print("-" * 112)
        return None

    mos_t, env_t = process_extra_temperature(et)

    # --- Save validated values ---
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
