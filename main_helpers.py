# main_helpers.py

import os
import sys
import json
import yaml
import shutil
import warnings
import importlib.util
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
