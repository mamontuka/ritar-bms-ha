# main_settings.py

# === Static limits ===
cell_min_limit = 2450
cell_max_limit = 4750

volt_min_limit = 40.00
volt_max_limit = 60.00

temp_min_limit = -20
temp_max_limit = 55

# === MQTT Device Info ===
MANUFACTURER = "Ritar Power"

# Batteries MQTT
BATTERY_BASE_TOPIC_TEMPLATE = "homeassistant/sensor/ritar_{index}"
BATTERY_DEVICE_MODEL_TEMPLATE = "Ritar Battery {index}"
BATTERY_DEVICE_IDENTIFIERS_TEMPLATE = ["ritar_{index}"]
BATTERY_UNIQUE_ID_TEMPLATE = "ritar_{index}_{suffix}"
BATTERY_OBJECT_ID_TEMPLATE = "ritar_{index}_{suffix}"

# ESS MQTT
ESS_BASE_TOPIC = "homeassistant/sensor/ritar_ess"
ESS_DEVICE_NAME = "Ritar ESS"
ESS_DEVICE_MODEL = "Energy Storage System"
ESS_DEVICE_IDENTIFIERS = ["ritar_ess"]
ESS_UNIQUE_ID_TEMPLATE = "ritar_ess_{suffix}"
ESS_OBJECT_ID_TEMPLATE = "ritar_ess_{suffix}"

# Inverter protocol
INVERTER_PROTOCOL_BASE_TOPIC = "homeassistant/select/ritar_ess/inverter_protocol"
INVERTER_PROTOCOL_UNIQUE_ID = "inverter_protocol"
INVERTER_PROTOCOL_OBJECT_ID = "inverter_protocol"

# File path to store zero_pad_cells state
PAD_STATE_PATH = "/data/last_pad_state.json"

# === Delta filtering thresholds ===
# These define how much a value must change before it's considered "new"

delta_filter = {
    'voltage': 0.1,           # V
    'current': 0.1,           # A
    'power': 1.0,             # W
    'temperature': 1.0,       # °C
    'mos_temperature': 1.0,   # °C
    'env_temperature': 1.0,   # °C
    'soc': 1.0,               # %
    'cycle': 1                # cycles
}
