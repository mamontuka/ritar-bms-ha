# === Polling throttle flag ===
pause_polling_until = 0

# === History and smoothing buffers ===
from collections import defaultdict  # for per-battery history tracking

# Per-battery history of SOCs and voltages for spike filtering
last_n_socs = defaultdict(list)      # now per-battery dict
last_n_voltages = defaultdict(list)  # now per-battery dict

# Per-battery temperature history for MOS and ENV
last_n_env = {}     # Already per-battery
last_n_mos = {}     # Already per-battery

history_len = 10  # number of values to keep for smoothing

# === Persistent fallback cache ===
last_valid_cycle_count = {}
last_valid_temps = {}
last_valid_extra = {}
last_valid_soc = {}
last_valid_voltage = {}
last_valid_current = {}
last_valid_power = {}
