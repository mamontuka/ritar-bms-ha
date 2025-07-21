# main_settings.py

# === Static operating limits ===
# These values define the acceptable physical operating ranges for the battery cells and the pack as a whole.
# They are used throughout the system for health validation, protection logic, and status reporting.
# Values outside these bounds may indicate battery degradation, sensor faults, or dangerous conditions.

cell_min_limit = 2700         # Minimum allowed voltage for a single cell (in millivolts)
cell_max_limit = 4700         # Maximum allowed voltage for a single cell (in millivolts)

volt_min_limit = 44.50        # Minimum allowed total pack voltage (in volts)
volt_max_limit = 58.50        # Maximum allowed total pack voltage (in volts)

temp_min_limit = -20          # Minimum allowed temperature for battery operation (in degrees Celsius)
temp_max_limit = 55           # Maximum allowed temperature for battery operation (in degrees Celsius)

# === MQTT Device Info ===
# These constants define MQTT topic templates and metadata used in Home Assistant autodiscovery.
# Templates support multi-battery setups by dynamically inserting the battery index and sensor type.

MANUFACTURER = "Ritar Power"  # Manufacturer name (used in MQTT discovery payloads)

# Per-battery MQTT topic and entity templates
BATTERY_BASE_TOPIC_TEMPLATE = "homeassistant/sensor/ritar_{index}"           # Base topic for battery sensor group
BATTERY_DEVICE_MODEL_TEMPLATE = "Ritar Battery {index}"                      # Device model label for Home Assistant
BATTERY_DEVICE_IDENTIFIERS_TEMPLATE = ["ritar_{index}"]                      # Unique ID for grouping sensor entities
BATTERY_UNIQUE_ID_TEMPLATE = "ritar_{index}_{suffix}"                        # Globally unique sensor entity ID
BATTERY_OBJECT_ID_TEMPLATE = "ritar_{index}_{suffix}"                        # Entity object_id used by HA internally

# ESS (Energy Storage System) global topic and entity templates
ESS_BASE_TOPIC = "homeassistant/sensor/ritar_ess"                            # Base topic for ESS-wide aggregated sensors
ESS_DEVICE_NAME = "Ritar ESS"                                                # Display name in Home Assistant UI
ESS_DEVICE_MODEL = "Energy Storage System"                                   # Device model shown in HA
ESS_DEVICE_IDENTIFIERS = ["ritar_ess"]                                       # Unique global identifier for the ESS
ESS_UNIQUE_ID_TEMPLATE = "ritar_ess_{suffix}"                                # Unique sensor ID per data type (voltage, current, etc.)
ESS_OBJECT_ID_TEMPLATE = "ritar_ess_{suffix}"                                # Home Assistant object ID per ESS sensor

# === Inverter protocol selector ===
# Allows selecting the inverter communication protocol from Home Assistant's UI (e.g., Victron, Growatt, Manual).
# This is published as a 'select' entity.

INVERTER_PROTOCOL_BASE_TOPIC = "homeassistant/select/ritar_ess/inverter_protocol"  # MQTT topic for inverter protocol selection
INVERTER_PROTOCOL_UNIQUE_ID = "inverter_protocol"                                  # Unique ID of the select entity
INVERTER_PROTOCOL_OBJECT_ID = "inverter_protocol"                                  # Home Assistant object ID for the entity

# === Cell indexing & zero-padding state file ===
# This file stores information about cell index gaps that were previously padded with zeros.
# When the number of detected cells changes (e.g., due to battery replacement or BMS misreporting),
# this ensures consistent array indexing across restarts and prevents MQTT sensors from shifting positions.
# Without this, cell_01 could suddenly become cell_02, breaking Home Assistant graphs and automations.

PAD_STATE_PATH = "/data/last_pad_state.json"    # Path to persistent file storing zero-padding state for cell list

# === Delta filtering thresholds ===
# These thresholds define the minimum change required for a new value to be published via MQTT.
# This reduces noise and MQTT traffic by filtering out insignificant fluctuations.
#
# Higher values apply stronger filtering — fewer updates, but potentially lower accuracy.
# This can lead to small gaps or step-like behavior on Home Assistant charts.
# Tune carefully depending on how much precision vs. performance you want.

delta_filter = {
    'voltage': 2.0,           # Minimum voltage change (V) required to trigger an update
    'current': 1.0,           # Minimum current change (A) to trigger an update
    'power': 1.0,             # Minimum power change (W) to trigger an update
    'temperature': 1.0,       # Minimum change in cell temperature (°C)
    'mos_temperature': 1.0,   # Minimum change in MOSFET temperature (°C)
    'env_temperature': 1.0,   # Minimum change in ambient/environment temperature (°C)
    'soc': 2.0,               # Minimum state-of-charge (%) change required
    'cycle': 1                # Battery cycle count must increase by this value to trigger an update
}
