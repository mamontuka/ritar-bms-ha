# main_arrays.py

# === Polling throttle flag ===
pause_polling_until = 0

# === History and smoothing buffers ===
last_n_socs = []
last_n_voltages = []
last_n_env = {}
last_n_mos = {}
history_len = 10  # number of values to keep for smoothing

# === Persistent fallback cache ===
last_valid_cycle_count = {}
last_valid_temps = {}
last_valid_extra = {}
last_valid_soc = {}
last_valid_voltage = {}
last_valid_current = {}
last_valid_power = {}
