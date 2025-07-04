# constants.py

import os
import sys
import json
import yaml
import warnings

# === Suppress deprecation warnings ===
warnings.filterwarnings("ignore", category=DeprecationWarning)

# === Static limits ===
cell_min_limit = 2450
cell_max_limit = 4750

volt_min_limit = 40.00
volt_max_limit = 60.00

temp_min_limit = -20
temp_max_limit = 55

# === Global pause flag (used to throttle polling for registers writes) ===
pause_polling_until = 0

# === History and smoothing buffers ===
last_n_socs = []
last_n_voltages = []
history_len = 5  # number of values to keep for smoothing

# === Persistent fallback cache ===
last_valid_cycle_count = {}
last_valid_temps = {}
last_valid_extra = {}
last_valid_soc = {}
last_valid_voltage = {}
last_valid_current = {}
last_valid_power = {}

# === Configuration loader ===
def load_config():
    """
    Loads configuration from Home Assistant add-on's options.json or fallback config.yaml.
    Ensures valid 'connection_type' is provided.
    """
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
