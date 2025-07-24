# main_arrays.py

# === Polling throttle flag ===
# Global timestamp (in seconds since epoch) indicating when polling is allowed to resume.
# Used to temporarily pause polling (e.g., in case of connection errors or timeouts).
pause_polling_until = 0

# === History and smoothing buffers ===
from collections import defaultdict  # Used for dynamically managing history per battery index

# Per-battery history buffers for smoothing and spike filtering
# These are short-term rolling arrays used to detect and suppress data glitches or noise.

last_n_socs = defaultdict(list)       # State of Charge (SOC) history for each battery
last_n_voltages = defaultdict(list)   # Voltage history for each battery

# Temperature history per battery, stored separately for:
last_n_env = {}  # Environmental/ambient temperature readings
last_n_mos = {}  # MOSFET temperature readings

history_len = 30  # Maximum number of recent values to keep per sensor, per battery
# Used to compute moving averages or detect sudden anomalies (spikes, dropouts)

# === Persistent fallback cache ===
# These dictionaries store the last known *valid* value for each sensor, per battery.
# If a new reading is invalid or missing, the fallback will be used for continuity.
# This helps avoid gaps or false zeroes in MQTT data or Home Assistant charts.

last_valid_cycle_count = {}  # Last known cycle count per battery
last_valid_temps = {}        # Last known temperature set (combined) per battery
last_valid_extra = {}        # Last known extra temperature readings per battery
last_valid_soc = {}          # Last known State of Charge (%)
last_valid_voltage = {}      # Last known voltage reading (V)
last_valid_current = {}      # Last known current (A)
last_valid_power = {}        # Last known power reading (W)
