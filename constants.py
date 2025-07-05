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

# === MQTT publishing configuration variables ===

# Equipment manufacturer MQTT labels
MANUFACTURER = "Ritar Power"
ESS_DEVICE_NAME = "Ritar ESS"
ESS_DEVICE_MODEL = "Energy Storage System"
ESS_DEVICE_IDENTIFIERS = ["ritar_ess"]

# Batteries MQTT sensor base and device info templates
BATTERY_BASE_TOPIC_TEMPLATE = "homeassistant/sensor/ritar_{index}"
BATTERY_DEVICE_MODEL_TEMPLATE = "Ritar Battery {index}"
BATTERY_DEVICE_IDENTIFIERS_TEMPLATE = ["ritar_{index}"]

# Unique and Object ID templates for batteries
BATTERY_UNIQUE_ID_TEMPLATE = "ritar_{index}_{suffix}"
BATTERY_OBJECT_ID_TEMPLATE = "ritar_{index}_{suffix}"

# ESS MQTT sensor base and device info
ESS_BASE_TOPIC = "homeassistant/sensor/ritar_ess"

# Unique and Object ID templates for ESS
ESS_UNIQUE_ID_TEMPLATE = "ritar_ess_{suffix}"
ESS_OBJECT_ID_TEMPLATE = "ritar_ess_{suffix}"

# Inverter protocol MQTT topics and device info
INVERTER_PROTOCOL_BASE_TOPIC = "homeassistant/select/ritar_ess/inverter_protocol"

# Unique and Object ID for inverter protocol (single device)
INVERTER_PROTOCOL_UNIQUE_ID = "inverter_protocol"
INVERTER_PROTOCOL_OBJECT_ID = "inverter_protocol"


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

# --- Helpers ---
def to_float(value, name):
    if isinstance(value, str):
        value = value.replace(',', '.')
    try:
        return float(value)
    except ValueError:
        sys.exit(f"Error: {name} must be a number, got {value}")

def validate_delay(cfg):
    qd = to_float(cfg.get('queries_delay', '0.1'), 'queries_delay')
    nb = to_float(cfg.get('next_battery_delay', '0.5'), 'next_battery_delay')
    return qd, nb
