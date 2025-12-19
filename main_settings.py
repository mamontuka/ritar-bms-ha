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

# History length for smoothing/filtering buffers (number of recent values kept per sensor per battery)
history_len = 30

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

# === Spike filter thresholds for raw data validation ===
spike_filter_delta = {
    'voltage': 2.0,           # Max allowed sudden jump in voltage before filtering spike
    'soc': 3.0                # Max allowed sudden jump in SOC before filtering spike
}

# ====================================
# === Battery parser configuration ===
# ====================================
# This section defines all configuration parameters used by the battery telemetry parser.
# These constants control how raw Modbus data is interpreted, filtered, and processed.
# They are critical for correct parsing, spike filtering, and validation of battery telemetry.

# ------------------------------
# Buffer lengths for Modbus responses
# ------------------------------
# Modbus queries return fixed-length byte arrays (buffers).
# These constants define how many bytes we expect for each type of response.
# If the received buffer length does not match these values, data may be considered invalid.
BLOCK_BUF_LEN = 37        # Length of the main telemetry block (contains voltage, current, SOC, cycle, power)
CELLS_BUF_LEN = 37        # Length of the block containing individual cell voltages
TEMP_BUF_LEN = 13         # Length of the block containing temperature sensors (standard)
EXTRA_TEMP_BUF_LEN = 25   # Length of the block containing extra temperature sensors (MOSFETs, ambient/environment)

# ------------------------------
# Minimum number of valid cells
# ------------------------------
# Sometimes individual cell readings may be missing or out-of-range.
# MIN_VALID_CELLS defines how many valid cells are required to accept the cell data.
MIN_VALID_CELLS = 8       # At least 8 valid cell voltages are needed to consider cell data usable

# ------------------------------
# Thresholds for discarding spikes
# ------------------------------
# Some readings may show unrealistic spikes due to communication errors or sensor glitches.
# These thresholds are used to discard extremely high values before processing.
MAX_CURRENT_SPIKE = 150    # Maximum allowable current in Amps; higher values are considered invalid
MAX_POWER_SPIKE = 8000     # Maximum allowable power in Watts; higher values are considered invalid

# ------------------------------
# Keys for spike filtering
# ------------------------------
# Spike filtering is applied selectively to certain metrics to remove sudden unrealistic jumps.
# These keys define which telemetry fields will undergo spike filtering.
SPIKE_FILTER_KEYS = ['voltage', 'soc']  # Only apply spike filtering to voltage and SOC

# ------------------------------
# Scaling factors for raw data
# ------------------------------
# Raw Modbus values are integers that need to be converted to meaningful units.
# For example, raw voltage = 5234 → actual voltage = 5234 / VOLTAGE_SCALE = 52.34 V
CURRENT_SCALE = 100  # Raw current values divided by 100 to get Amps
VOLTAGE_SCALE = 100  # Raw voltage values divided by 100 to get Volts
SOC_SCALE = 10       # Raw SOC values divided by 10 to get percent (e.g., 855 → 85.5%)

# ------------------------------
# Hex offsets in the main block
# ------------------------------
# Each telemetry field is located at a specific byte range in the main telemetry block.
# These offsets define the start and end positions for slicing the hex string representation of the block.
OFFSET_CURRENT_START = 6    # Current data starts at byte 6
OFFSET_CURRENT_END   = 10   # Current data ends at byte 10 (exclusive) — 4 bytes total

OFFSET_VOLTAGE_START = 10   # Voltage data starts at byte 10
OFFSET_VOLTAGE_END   = 14   # Voltage data ends at byte 14 (exclusive)

OFFSET_SOC_START     = 14   # SOC data starts at byte 14
OFFSET_SOC_END       = 18   # SOC data ends at byte 18 (exclusive)

OFFSET_CYCLE_START   = 34   # Cycle count starts at byte 34
OFFSET_CYCLE_END     = 38   # Cycle count ends at byte 38 (exclusive)

# ------------------------------
# Cell parsing offsets
# ------------------------------
# Each individual cell voltage is also stored in a fixed position within the cells buffer.
# The following constants allow sequential extraction of all cell voltages.
NUM_CELLS       = 16      # Total number of cells in the battery
CELL_HEX_OFFSET = 6       # Starting byte of the first cell's voltage data
CELL_HEX_STEP   = 4       # Each cell occupies 4 bytes
CELL_HEX_END    = 10      # Ending byte of the first cell's data (exclusive)
# For each subsequent cell, the start and end positions are calculated as:
# start = CELL_HEX_OFFSET + CELL_HEX_STEP * i
# end   = CELL_HEX_END + CELL_HEX_STEP * i
# where i = 0..NUM_CELLS-1

# ------------------------------
# Console output formatting
# ------------------------------
# Length of the separator line printed in the console for readability.
CONSOLE_SEPARATOR_LEN = 112

# ------------------------------
# SOC bounds
# ------------------------------
# Define the valid range of the State of Charge (SOC) in percent.
# Values outside this range are considered invalid or erroneous.
SOC_MIN = 0
SOC_MAX = 100

# ------------------------------
# Template for parsed result
# ------------------------------
# When parsing telemetry, we always return a dictionary with the following keys.
# Initially, all values are None and will be filled with actual readings if valid.
RESULT_TEMPLATE = {
    'voltage': None,  # Battery pack voltage in Volts
    'soc': None,      # State of Charge in percent
    'cycle': None,    # Battery cycle count
    'current': None,  # Current in Amps
    'power': None,    # Power in Watts
    'cells': None,    # List of individual cell voltages (millivolts)
    'temps': None     # List of temperatures from standard sensors (°C)
}

# === Temperature parsing and spike filtering configuration ===
# These constants define how raw temperature data from the battery is interpreted,
# converted to Celsius, and filtered for spikes. Centralizing them here allows
# easy tuning without touching parser logic.

# --- Buffer structure ---
TEMP_HEADER_BYTES = 3          # Number of header bytes to skip at the start of temperature buffer
TEMP_FOOTER_BYTES = 2          # Number of footer bytes to skip at the end of temperature buffer
TEMP_BYTE_STEP = 2             # Number of bytes per single temperature reading in the buffer

# --- Raw to Celsius conversion ---
TEMP_RAW_OFFSET = 726          # Offset to subtract from raw sensor value (specific to MOS/ENV sensor)
TEMP_SCALE = 0.1               # Scale factor to convert raw units to degrees Celsius
TEMP_BASE_OFFSET = 22.6        # Base offset added after scaling (calibration value)
TEMP_ROUND_DIGITS = 1          # Number of decimal digits to round temperature readings

# --- Extra temperature buffer (MOSFET / ENV sensors) ---
EXTRA_TEMP_BUF_LEN = 25        # Expected length of the extra temperature buffer
# Indices in the hex string (not raw bytes) of MOS/ENV temperatures
MOS_HEX_START = 6              # Start index in hex string for MOS temperature (inclusive)
MOS_HEX_END   = 10             # End index in hex string for MOS temperature (exclusive)
ENV_HEX_START = 10             # Start index in hex string for ENV temperature (inclusive)
ENV_HEX_END   = 14             # End index in hex string for ENV temperature (exclusive)

# --- Spike filtering ---
DELTA_TEMP_LIMIT = 1.0         # Maximum allowed difference between consecutive readings
                               # beyond which a value is considered a spike and rejected

# --- MQTT temperatures publication filter ---
TEMP_MQTT_LIMIT = 0.5          # Maximum allowed difference betwen previous value and current
                               # used with RS485-ethernet/serial connection types,
                               # overriden with bluetooth connection.
