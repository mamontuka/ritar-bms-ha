# modbus_registers.py

from typing import Dict

# Battery register addresses and lengths
REG_BLOCK_VOLTAGE       = 0x0000
REG_CELLS_VOLTAGE       = 0x0028
REG_TEMPERATURE         = 0x0078
REG_EXTRA_TEMPERATURE   = 0x0091

LEN_BLOCK_VOLTAGE       = 0x10
LEN_CELLS_VOLTAGE       = 0x10
LEN_TEMPERATURE         = 0x04
LEN_EXTRA_TEMPERATURE   = 0x0A

# Inverter register addresses
REG_INVERTER_PROTOCOL = 0x0020

# Modbus function codes
FUNC_READ_HOLDING_REGS = 0x03
FUNC_WRITE_MULTIPLE_REGS = 0x10
FUNC_WRITE_SINGLE_REG = 0x06

INVERTER_PROTOCOLS = {
    0: "RITAR_RS485 (RITARV1_8)",
    1: "DEYE_RS485 (Deye BMS Protocol 12), PLY(DEYE,SMK,FIRMAN,Hollandia)",
    2: "GROWATT_RS485",
    3: "VOLTRONIC_RS485, LIB05(VOLTRONIC,XUNZEL,TESLA,GSB SOLAR,PCE)",
    4: "UPOWER_RS485",
    5: "VERTIV_RS485",
    6: "ELTEK_RS485",
    7: "RITAR_MODBUSV1_9_RS485",
    8: "VICTRON_CAN",
    9: "RITAR_CAN",
    10: "SMA_CAN (Deye BMS Protocol 00)",
    11: "MEGAREVO_CAN",
    12: "TBB_CAN",
    13: "SOLIS_CAN",
    14: "INHENERGY_RS485",
    15: "MUST_CAN",
    16: "PYON_CAN",
    17: "LUXPOWERTEK_RS485",
    18: "PHOCOS_RS485",
}

# Register groups with keys and their register addresses
PRESET_GROUPS: Dict[str, Dict[str, int]] = {
    "general": {
        "current": 0,
        "voltage_of_pack": 1,
        "soc": 2,
        "soh": 3,
        "remain_capacity": 4,
        "full_capacity": 5,
        "design_capacity": 6,
        "battery_cycle_counts": 7,
        "solar_current": 8,
        "warning_flag_high": 9,
        "warning_flag_low": 10,
        "protection_flag_high": 11,
        "protection_flag_low": 12,
        "status_fault_flag_high": 13,
        "status_fault_flag_low": 14,
        "balance_status": 15,
        "mac": 20,
    },
    "charger_and_inverter": {
        "charger_voltage": 31,
        "inverter_select": 32,
        "total_current": 33,
    },
    "cell_voltages": {
        "cell_voltage": 40,
        "cell_max_voltage": 147,
        "cell_max_voltage_number": 148,
        "cell_min_voltage": 149,
        "cell_min_voltage_number": 150,
    },
    "cell_temperature": {
        "cell_temperature": 120,
        "cell_max_temperature": 151,
        "cell_max_temperature_number": 152,
        "cell_min_temperature": 153,
        "cell_min_temperature_number": 154,
        "positive_temperature": 155,
        "negative_temperature": 156,
    },
    "pack_over_voltage": {
        "pack_ov_alarm": 160,
        "pack_ov_protection": 161,
        "pack_ov_release_protection": 162,
        "pack_ov_protection_delay_time": 163,
    },
    "cell_over_voltage": {
        "cell_ov_alarm": 164,
        "cell_ov_protection": 165,
        "cell_ov_release_protection": 166,
        "cell_ov_protection_delay_time": 167,
    },
    "pack_under_voltage": {
        "pack_uv_alarm": 168,
        "pack_uv_protection": 169,
        "pack_uv_release_protection": 170,
        "pack_uv_protection_delay_time": 171,
    },
    "cell_under_voltage": {
        "cell_uv_alarm": 172,
        "cell_uv_protection": 173,
        "cell_uv_release_protection": 174,
        "cell_uv_protection_delay_time": 175,
    },
    "charging_over_current": {
        "charging_oc_alarm": 176,
        "charging_oc_protection": 177,
        "charging_oc_protection_delay_time": 178,
        "charging_oc2_protection": 213,
        "charging_oc2_protection_delay_time": 214,
    },
    "discharging_over_current": {
        "discharging_oc_alarm": 179,
        "discharging_oc_protection": 180,
        "discharging_oc_protection_delay_time": 181,
        "discharging_oc2_protection": 182,
        "discharging_oc2_protection_delay_time": 183,
    },
    "charging_over_temperature": {
        "charging_ot_alarm": 184,
        "charging_ot_protection": 185,
        "charging_ot_release_protection": 186,
    },
    "discharging_over_temperature": {
        "discharging_ot_alarm": 187,
        "discharging_ot_protection": 188,
        "discharging_ot_release_protection": 189,
    },
    "charging_under_temperature": {
        "charging_ut_alarm": 190,
        "charging_ut_protection": 191,
        "charging_ut_release_protection": 192,
    },
    "discharging_under_temperature": {
        "discharging_ut_alarm": 193,
        "discharging_ut_protection": 194,
        "discharging_ut_release_protection": 195,
    },
    "mosfet_temperature": {
        "mosfet_ot_alarm": 196,
        "mosfet_ot_protection": 197,
        "mosfet_ot_release_protection": 198,
    },
    "environment_temperature": {
        "environment_ot_alarm": 199,
        "environment_ot_protection": 200,
        "environment_ot_release_protection": 201,
        "environment_ut_alarm": 202,
        "environment_ut_protection": 203,
        "environment_ut_release_protection": 204,
    },
    "balance": {
        "balance_start_cell_voltage": 205,
        "balance_start_delta_voltage": 206,
    },
    "pack_charge": {
        "pack_full_charge_voltage": 207,
        "pack_full_charge_current": 208,
    },
    "cell_sleep": {
        "cell_sleep_voltage": 209,
        "cell_sleep_delay_time": 210,
        "short_circuit_protect_delay_time": 211,
        "soc_alarm_threshold": 212,
    },
    "battery_status": {
        "soc1": 215,
        "soc2": 216,
        "soh1": 217,
        "soh2": 218,
        "remain_capacity1": 219,
        "remain_capacity2": 220,
        "full_capacity1": 221,
        "full_capacity2": 222,
    },
    "calibration": {
        "afe_current_zero": 223,
        "afe_pos_current_calib": 224,
        "afe_neg_current_calib": 225,
        "mcu_current_zero": 226,
        "mcu_pos_current_calib": 227,
        "mcu_neg_current_calib": 228,
        "pack_voltage_zero": 229,
        "pack_voltage_calib": 230,
    },
    "mosfet_control": {
        "charge_mos_control": 231,
        "discharge_mos_control": 232,
        "pre_mos_control": 233,
        "fan_mos_control": 234,
        "limit_mos_control": 235,
        "dry_contact1_control": 236,
        "dry_contact2_control": 237,
        "pc_mos_control": 238,
        "fs_mos_control": 287,
    },
    "datetime": {
        "year": 239,
        "month": 240,
        "day": 241,
        "hour": 242,
        "minute": 243,
        "second": 244,
    },
    "restore_and_record": {
        "restore_default_parameters": 245,
        "record_length": 246,
        "record_history": 247,
    },
    "sleep": {
        "sleep": 280,
    },
    "pn_over_temperature": {
        "pn_ot_alarm": 283,
        "pn_ot_protect": 284,
        "pn_ot_release": 285,
        "pn_ot_delay": 286,
    },
    "version_info": {
        "version_information": 290,
        "model_sn": 300,
        "pack_sn": 310,
        "end": 320,
    },
    "unknown": {
        # Any registers not fitting above groups or gaps can be added here if needed
    },
}

# List of groups to fully block from writing and reading from EEPROM at start
BLOCKED_GROUPS = [
    "general",
    "charger_and_inverter",
    "cell_voltages",
    "cell_under_voltage",
    "cell_temperature",
    "charging_over_current",
    "discharging_over_current",
    "charging_over_temperature",
    "discharging_over_temperature",
    "charging_under_temperature",
    "discharging_under_temperature",
    "mosfet_temperature",
    "environment_temperature",
    "battery_status",
    "calibration",
    "mosfet_control",
    "datetime",
    "restore_and_record",
    "sleep",
    "pn_over_temperature",
    "version_info",
    "unknown",
]

# Individual dangerous registers (optional extra keys)
INDIVIDUAL_DANGEROUS_REGISTERS = {
    # e.g. "pack_full_charge_voltage",
        "pack_full_charge_current",
}

# Mapping of keywords to (unit, device_class)
PRESET_UNITS_DEVICE_CLASSES = {
    "voltage": ("mV", "voltage"),
    "current": ("A", "current"),
    "temperature": ("°C", "temperature"),
    "capacity": ("Ah", None),
    "soc": ("%", "battery"),
    "count": (None, None),
    "time": ("ms", None),
    "power": ("W", "power"),
    "_ov_": ("mV", "voltage"),
    "_uv_": ("mV", "voltage"),
    # add more as needed...
}

# Build full set of dangerous registers from blocked groups and individual keys
DANGEROUS_REGISTERS = set(INDIVIDUAL_DANGEROUS_REGISTERS)
for group_name in BLOCKED_GROUPS:
    group = PRESET_GROUPS.get(group_name)
    if group:
        DANGEROUS_REGISTERS.update(group.keys())

# End of file
