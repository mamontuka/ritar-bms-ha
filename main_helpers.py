# main_helpers.py

import os
import sys
import json
import yaml
import shutil
import warnings
from main_settings import PAD_STATE_PATH

# === Suppress deprecation warnings globally ===
warnings.filterwarnings("ignore", category=DeprecationWarning)

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

def has_zeropad_changed(current_value):
    """Detect if the zero_pad_cells setting has changed."""
    if os.path.exists(PAD_STATE_PATH):
        try:
            with open(PAD_STATE_PATH, "r") as f:
                prev = json.load(f)
                return prev.get("zero_pad_cells") != current_value
        except Exception:
            return True
    return not os.path.exists(PAD_STATE_PATH)

def save_zeropad_state(current_value):
    """Store the current zero_pad_cells setting."""
    try:
        tmp_path = PAD_STATE_PATH + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump({"zero_pad_cells": current_value}, f)
        shutil.move(tmp_path, PAD_STATE_PATH)
    except Exception as e:
        print(f"[WARN] Cannot save pad state: {e}")
