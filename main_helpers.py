# main_helpers.py

import os
import sys
import json
import yaml
import shutil
import warnings
import importlib.util
from statistics import median
from main_settings import PAD_STATE_PATH

# === Suppress deprecation warnings globally ===
warnings.filterwarnings("ignore", category=DeprecationWarning)

# === Configuration loader ===
def load_config():
    """Load configuration from options.json or fallback config.yaml."""
    if os.path.exists('/data/options.json'):
        with open('/data/options.json') as f:
            cfg = json.load(f)
    elif os.path.exists('config.yaml'):
        with open('config.yaml') as f:
            y = yaml.load(f, Loader=yaml.FullLoader)
            cfg = y.get('options', {})
    else:
        sys.exit("Error: No config file found")

    if cfg.get('connection_type') not in ('ethernet', 'serial'):
        sys.exit("Error: connection_type must be 'ethernet' or 'serial'")

    return cfg

# === Validators for wrong values writen by user in addon configuration ===
def to_float(value, name):
    """Convert value to float, handling commas and validation."""
    if isinstance(value, str):
        value = value.replace(',', '.')
    try:
        return float(value)
    except ValueError:
        sys.exit(f"Error: {name} must be a number, got {value}")

def validate_delay(cfg):
    """Parse and return validated delay settings."""
    qd = to_float(cfg.get('queries_delay', '0.1'), 'queries_delay')
    nb = to_float(cfg.get('next_battery_delay', '0.5'), 'next_battery_delay')
    return qd, nb

# === zero_pad_cells persistent flag check ===
def has_zeropad_changed(current_value, pad_state_path):
    """
    Check if the zero_pad_cells setting has changed compared to the saved state.

    Args:
        current_value (bool): Current zero_pad_cells setting from config.
        pad_state_path (str): Path to the JSON file storing previous zero_pad_cells state.

    Returns:
        bool: True if the zero_pad_cells value has changed or file does not exist,
              False if it is the same as previous saved state.
    """
    if os.path.exists(pad_state_path):
        try:
            with open(pad_state_path, "r") as f:
                prev = json.load(f)
                return prev.get("zero_pad_cells") != current_value
        except Exception:
            # If file corrupted or unreadable, assume changed to be safe
            return True
    # File does not exist means first run or state unknown => considered changed
    return True

# === zero_pad_cells persistent flag save ===
def save_zeropad_state(current_value, pad_state_path):
    """
    Save the current zero_pad_cells setting persistently to a JSON file.

    Args:
        current_value (bool): Current zero_pad_cells setting to save.
        pad_state_path (str): Path to the JSON file where the state will be saved.
    """
    try:
        tmp_path = pad_state_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump({"zero_pad_cells": current_value}, f)
        shutil.move(tmp_path, pad_state_path)
    except Exception as e:
        print(f"[WARN] Cannot save pad state: {e}")

# === United BMS custom modules loader ===
def try_import_custom_module(module_name, custom_dir):
    """Try importing a module from custom_dir, or fall back to internal module."""
    if not custom_dir:
        print(f"[INFO] No custom path provided. Using internal {module_name}.py")
        return __import__(module_name)

    module_path = os.path.join(custom_dir, f"{module_name}.py")

    # === Check for zero-size override file ===
    if os.path.isfile(module_path) and os.path.getsize(module_path) == 0:
        print(f"[ERROR] Custom override file {module_path} is empty. Cannot continue.")
        sys.exit(1)  # Immediately stop execution

    if os.path.exists(module_path):
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                print(f"[INFO] Loaded override {module_name}.py from {module_path}")
                return module
        except Exception as e:
            print(f"[ERROR] Failed to import override {module_name} from {module_path}: {e}")
            sys.exit(1)  # Exit on import error

    # === Try internal fallback ===
    try:
        module = __import__(module_name)
        real_path = module.__file__ if hasattr(module, '__file__') else "(built-in)"
        print(f"[INFO] Loaded internal {module_name}.py from {real_path}")
        return module
    except Exception as e:
        print(f"[ERROR] Failed to load internal module {module_name}: {e}")
        sys.exit(1)

# === United BMS protect functions ===
def get_optional_attr(module, attr_name, default=None, warn_if_missing=True):
    """
    Safely gets an attribute from a module. Returns default if not found.
    If warn_if_missing is True, prints a warning if attribute is missing.
    """
    if module is None:
        return default
    try:
        return getattr(module, attr_name)
    except AttributeError:
        if warn_if_missing:
            print(f"[WARN] Module '{module.__name__}' does not have attribute '{attr_name}'")
        return default

# === Spike filter helper ===
def filter_spikes(new_value, last_values, max_delta):
    """
    Filter out spikes in sensor data that differ too much from recent history.

    If no history, accept new_value.
    If deviation from median of last_values is above max_delta, return previous stable median.
    Otherwise, return new_value.
    """
    if new_value is None:
        return None
    if not last_values:
        return new_value
    last_median = median(last_values)  # use median
    if abs(new_value - last_median) > max_delta:
        return last_median  # return stable value instead of rejecting entirely
    return new_value

# === Helper to validate numeric values before caching and publishing ===
def is_valid_number(val, minv=None, maxv=None):
    if val is None or not isinstance(val, (int, float)):
        return False
    if minv is not None and val < minv:
        return False
    if maxv is not None and val > maxv:
        return False
    return True

# === Battery readings results processing, filter values and accumulate sums ===
def process_battery(
    i, mos_t, env_t, main_settings, history_len,
    last_valid_soc, last_valid_voltage, last_valid_current, last_valid_power,
    last_n_socs, last_n_voltages, last_n_env, last_n_mos,
    delta_filter, filter_spikes, filter_temperature_spikes,
    valid_socs, valid_voltages, valid_env, valid_mos
):
    """
    Process filtering and accumulation for a single battery.
    This function was moved from main.py for better modularity.
    """

    # --- SOC spike filtering ---
    if filter_spikes and i in last_valid_soc:
        filtered_soc = filter_spikes(
            last_valid_soc[i],
            last_n_socs[i],
            max_delta=delta_filter.get("soc", 5)
        )
        if filtered_soc is not None:
            last_n_socs[i].append(filtered_soc)
            if len(last_n_socs[i]) > history_len:
                last_n_socs[i].pop(0)
            valid_socs.append(filtered_soc)

    # --- Voltage spike filtering ---
    if filter_spikes and i in last_valid_voltage:
        filtered_voltage = filter_spikes(
            last_valid_voltage[i],
            last_n_voltages[i],
            max_delta=delta_filter.get("voltage", 1.0)
        )
        if filtered_voltage is not None:
            last_n_voltages[i].append(filtered_voltage)
            if len(last_n_voltages[i]) > history_len:
                last_n_voltages[i].pop(0)
            valid_voltages.append(filtered_voltage)

    # --- MOS temperature spike filtering ---
    if filter_temperature_spikes and mos_t is not None:
        if i not in last_n_mos:
            last_n_mos[i] = []
        filtered_mos_list = filter_temperature_spikes(
            [mos_t], last_n_mos[i],
            main_settings.temp_min_limit, main_settings.temp_max_limit,
            delta_limit=delta_filter.get("mos_temperature", 1.0)
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
            delta_limit=delta_filter.get("env_temperature", 1.0)
        )
        filtered_env = filtered_env_list[0]
        if filtered_env is not None:
            last_n_env[i].append(filtered_env)
            if len(last_n_env[i]) > history_len:
                last_n_env[i].pop(0)
            valid_env.append(filtered_env)

    # --- Accumulate current and power for summary ---
    current = last_valid_current.get(i)
    power = last_valid_power.get(i)
    return current, power

# === Get number of cells from add-on config with fallback ===
def get_num_cells_from_config(default=16, min_cells=8, max_cells=16, config_path="/data/options.json"):
    """
    Read number of cells from add-on configuration.
    Returns default if missing or out of bounds.
    Allowed range: min_cells..max_cells
    """
    if not os.path.exists(config_path):
        return default
    try:
        with open(config_path, "r") as f:
            cfg = json.load(f)
        n = int(cfg.get("num_cells", default))
        if n < min_cells or n > max_cells:
            print(f"[INFO] Invalid num_cells in config ({n}), using default {default}")
            return default
        return n
    except Exception as e:
        print(f"[WARN] Failed to read num_cells from config: {e}. Using default {default}")
        return default
