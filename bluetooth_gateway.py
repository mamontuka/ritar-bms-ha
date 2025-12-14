# bluetooth_gateway.py
# Synchronous Bluetooth bridge for Ritar BMS
# ------------------------------------------------------------------------------
# - Low-level spike filtering for core metrics (voltage, SOC, current, power)
# - Correct sign display for console and MQTT:
#   - negative → discharge
#   - positive/0 → no sign
# ------------------------------------------------------------------------------

import time
import json
from websocket import create_connection, WebSocketTimeoutException

from bluetooth_battery import BATTERIES_CONFIG
from main_arrays import (
    last_valid_voltage, last_valid_soc, last_valid_current, last_valid_power,
    last_valid_cycle_count, last_n_voltages, last_n_socs,
)
from main_helpers import filter_spikes, is_valid_number
from main_settings import spike_filter_delta, history_len

# ----------------------
# TEMPERATURE TABLE (RAW hex -> °C)
# ----------------------
RAW_TO_C = {f"{0x3F + (c - 23):02X}": c for c in range(-20, 61)}

ZERO_CURRENT_RAW = 30000
CURRENT_SCALE = 0.1000

# ----------------------
# PARSERS
# ----------------------
def parse_block_notify(notify_hex: str):
    parts = notify_hex.split()
    if len(parts) < 24:
        return None, None, None, None, None
    data = parts[3:]
    try:
        block_voltage = int(data[0] + data[1], 16) / 10.0
        soc = int(data[4] + data[5], 16) / 10.0
        cycles = int(data[22] + data[23], 16)
        mos_t_raw = int(data[12] + data[13], 16)
        env_t_raw = int(data[13], 16)
        mos_t = RAW_TO_C.get(f"{mos_t_raw:02X}", 0)
        env_t = RAW_TO_C.get(f"{env_t_raw:02X}", 0)
        if env_t is not None:
            env_t += 2
    except Exception:
        return None, None, None, None, None
    return block_voltage, soc, cycles, mos_t, env_t

def parse_cells_notify(notify_hex: str):
    parts = notify_hex.split()
    if len(parts) < 36:
        return [], [], []
    data_bytes = parts[3:]
    voltages = []
    for i in range(0, 32, 2):
        try:
            voltages.append(int(data_bytes[i] + data_bytes[i+1], 16))
        except Exception:
            voltages.append(0)
    temps = []
    try:
        temp_bytes = data_bytes[64:72]
        for i in range(1, 8, 2):
            temps.append(RAW_TO_C.get(temp_bytes[i], 0))
    except Exception:
        temps = [0, 0, 0, 0]
    return voltages, temps, data_bytes

def parse_block_current(data_bytes):
    try:
        raw = int(data_bytes[2] + data_bytes[3], 16)
        # negative → discharge, positive/0 → charge/0 (display handled later)
        current = -((raw - ZERO_CURRENT_RAW) * CURRENT_SCALE)
        return round(current, 2)
    except Exception:
        return None

# ----------------------
# BluetoothBridge class
# ----------------------
class BluetoothBridge:
    def __init__(self, config=None):
        self.config = config or {}
        self.gate_url = f"ws://{self.config.get('bluetooth_gate_ip', '192.168.0.101')}:{self.config.get('bluetooth_gate_port', 50501)}/"
        self.num_batteries = int(self.config.get("num_batteries", len(BATTERIES_CONFIG)))
        self.num_batteries = max(1, min(self.num_batteries, len(BATTERIES_CONFIG)))
        self.active_batteries = BATTERIES_CONFIG[:self.num_batteries]

        self.delay_between_cmds = float(self.config.get("bluetooth_delay_between_query", 0.5))
        self.cmd_timeout = float(self.config.get("bluetooth_answer_wait_timeout", 2.0))
        self.next_battery_delay = float(self.config.get("bluetooth_next_battery_delay", 3.0))

        self.console_output_enabled = bool(self.config.get("console_output_enabled", False))
        self.warnings_enabled = bool(self.config.get("warnings_enabled", False))

    def _find_cfg_for_battery(self, index):
        for cfg in self.active_batteries:
            if cfg.get("battery_num") == index:
                return cfg
        return None

    def read_battery(self, index, console_output_enabled=None, warnings_enabled=None, mqtt_publish_func=None):
        if console_output_enabled is None:
            console_output_enabled = self.console_output_enabled
        if warnings_enabled is None:
            warnings_enabled = self.warnings_enabled

        cfg = self._find_cfg_for_battery(index)
        if not cfg:
            if warnings_enabled:
                print(f"[BT] No command config for battery {index}")
            return None

        data_dict = {'voltage': None, 'soc': None, 'cycle': None, 'current': None,
                     'power': None, 'cells': None, 'temps': None}
        mos_t = None
        env_t = None

        try:
            ws = create_connection(self.gate_url, timeout=self.cmd_timeout)
            try:
                ws.send(json.dumps({"cmd": "set_mode python-driven"}))
            except Exception:
                pass

            for cmd in cfg.get("cmds", []):
                try:
                    ws.send(json.dumps({"cmd": cmd}))
                except Exception:
                    if warnings_enabled:
                        print(f"[BT] Failed to send cmd for battery {index}: {cmd}")
                    time.sleep(self.delay_between_cmds)
                    continue

                start_time = time.time()
                while True:
                    if time.time() - start_time > self.cmd_timeout:
                        break
                    try:
                        message = ws.recv()
                    except WebSocketTimeoutException:
                        break
                    except Exception:
                        break
                    if not message:
                        break

                    try:
                        j = json.loads(message)
                        notify = j.get("notify")
                        if not notify:
                            continue
                    except Exception:
                        continue

                    parts = notify.split()
                    if len(parts) < 3:
                        continue
                    third_byte = parts[2]

                    if third_byte == "4E":
                        voltages, temps, _ = parse_cells_notify(notify)
                        if voltages:
                            data_dict['cells'] = voltages
                        if temps:
                            data_dict['temps'] = temps
                    else:
                        block_v, soc_val, cycles_val, mos_val, env_val = parse_block_notify(notify)
                        data_bytes = parts[3:]
                        current_val = parse_block_current(data_bytes)
                        power_val = round(block_v * current_val, 2) if (block_v is not None and current_val is not None) else None

                        data_dict.update({
                            'voltage': block_v,
                            'soc': soc_val,
                            'cycle': cycles_val,
                            'current': current_val,
                            'power': power_val
                        })
                        mos_t = mos_val
                        env_t = env_val

            try:
                ws.close()
            except Exception:
                pass

            idx = index

            # ----------------------
            # SPIKE FILTERING (voltage/SOC)
            # ----------------------
            if is_valid_number(data_dict['voltage']):
                filtered_voltage = filter_spikes(data_dict['voltage'], last_n_voltages[idx], spike_filter_delta['voltage'])
                if filtered_voltage is not None:
                    data_dict['voltage'] = filtered_voltage
                    last_n_voltages[idx].append(filtered_voltage)
                    if len(last_n_voltages[idx]) > history_len:
                        last_n_voltages[idx].pop(0)
                last_valid_voltage[idx] = data_dict['voltage']
            else:
                data_dict['voltage'] = last_valid_voltage.get(idx)

            if is_valid_number(data_dict['soc']):
                filtered_soc = filter_spikes(data_dict['soc'], last_n_socs[idx], spike_filter_delta['soc'])
                if filtered_soc is not None:
                    data_dict['soc'] = filtered_soc
                    last_n_socs[idx].append(filtered_soc)
                    if len(last_n_socs[idx]) > history_len:
                        last_n_socs[idx].pop(0)
                last_valid_soc[idx] = data_dict['soc']
            else:
                data_dict['soc'] = last_valid_soc.get(idx)

            # ----------------------
            # Current / Power
            # ----------------------
            if is_valid_number(data_dict['current']):
                last_valid_current[idx] = data_dict['current']
            else:
                data_dict['current'] = last_valid_current.get(idx)

            if is_valid_number(data_dict['power']):
                last_valid_power[idx] = data_dict['power']
            else:
                data_dict['power'] = last_valid_power.get(idx)

            # ----------------------
            # MOS / ENV temperatures filtering
            # ----------------------
            if mos_t is not None and not (0 <= mos_t <= 100):
                mos_t = None
            if env_t is not None and not (0 <= env_t <= 60):
                env_t = None

            # ----------------------
            # Skip incomplete/misread data
            # ----------------------
            mandatory_fields = ['voltage', 'soc', 'current', 'power', 'cycle', 'cells']
            if any(data_dict.get(f) is None for f in mandatory_fields):
                if warnings_enabled:
                    print(f"[WARN] Battery {index} incomplete or invalid, skipping MQTT publish/console")
                return None

            # ----------------------
            # Correct sign display
            # ----------------------
            def normalize_zero(val):
                """Convert -0.0 to 0.0 for both console and MQTT"""
                if val is None:
                    return None
                if abs(val) < 0.0001:
                    return 0.0
                return val

            # normalize current/power floats before display and MQTT
            data_dict['current'] = normalize_zero(data_dict['current'])
            data_dict['power'] = normalize_zero(data_dict['power'])

            cur_display = str(data_dict['current'])
            pow_display = str(data_dict['power'])

            # ----------------------
            # Console output
            # ----------------------
            if console_output_enabled:
                print(f"Battery {index} SOC: {data_dict['soc']} %, Voltage: {data_dict['voltage']} V, "
                      f"Cycles: {data_dict['cycle']}, Current: {cur_display} A, Power: {pow_display} W")
                if data_dict.get('cells'):
                    print(f"Battery {index} Cells: {', '.join(str(v) for v in data_dict['cells'])}")
                if data_dict.get('temps'):
                    print(f"Battery {index} Temps: {', '.join(str(t) for t in data_dict['temps'])}°C")
                if mos_t is not None or env_t is not None:
                    print(f"Battery {index} MOS Temp: {mos_t}°C, ENV Temp: {env_t}°C")
                print("-" * 112)

            # ----------------------
            # MQTT publish (if function provided)
            # ----------------------
            if mqtt_publish_func:
                mqtt_publish_func(index, {
                    'voltage': data_dict['voltage'],
                    'soc': data_dict['soc'],
                    'cycle': data_dict['cycle'],
                    'current': cur_display,
                    'power': pow_display,
                    'cells': data_dict.get('cells'),
                    'temps': data_dict.get('temps'),
                    'mos_temp': mos_t,
                    'env_temp': env_t
                })

            time.sleep(self.next_battery_delay)
            return data_dict, mos_t, env_t

        except Exception as e:
            if warnings_enabled:
                print(f"[ERROR] Bluetooth read failed for battery {index}: {e}")
            return None
