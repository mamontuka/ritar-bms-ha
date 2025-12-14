# bluetooth_battery.py

# Commands configuration for all Ritar BMS bluetooth batteries

# ----------------------
# CONFIGURABLE BATTERIES
# For batteries 1..8 define their unique command sets.
# ----------------------
BATTERIES_CONFIG = [
    { "battery_num": 1, "cmds": [
        "D2 10 00 CC 00 03 19 0B 0C 00 11 05 55 75",    # wakeup packet, need once for master battery
        "D2 03 00 80 00 01 96 41",                      # battery D2 (modbus ID #1) ping
        "D2 03 00 28 00 17 96 6F",                      # block information query
        "D2 03 00 00 00 27 16 73"                       # cells & cells temps query
    ]},
    { "battery_num": 2, "cmds": [
        "D3 03 00 80 00 01 97 90",                      # battery D3 (modbus ID #2) ping
        "D3 03 00 28 00 17 97 BE",                      # block infoemation query
        "D3 03 00 00 00 27 17 A2"                       # cells & cells temps query
    ]},
    { "battery_num": 3, "cmds": [
        "D4 03 00 80 00 01 96 27",                      # battery D4 (modbus ID #3) ping
        "D4 03 00 28 00 17 96 09",                      # block information query
        "D4 03 00 00 00 27 16 15"                       # cells & cells temps query
    ]},
    { "battery_num": 4, "cmds": [
        "D5 03 00 80 00 01 97 F6",                      # battery D5 (modbus ID #4) ping
        "D5 03 00 28 00 17 97 D8",                      # block information query
        "D5 03 00 00 00 27 17 C4"                       # cells & cells temps query
    ]},
    { "battery_num": 5, "cmds": [
        "D6 03 00 80 00 01 97 C5",                      # battery D6 (modbus ID #5) ping
        "D6 03 00 28 00 17 97 EB",                      # block information query
        "D6 03 00 00 00 27 17 F7"                       # cells & cells temps query
    ]},
    { "battery_num": 6, "cmds": [
        "D7 03 00 80 00 01 96 14",                      # battery D7 (modbus ID #6) ping
        "D7 03 00 28 00 17 96 3A",                      # block information query
        "D7 03 00 00 00 27 16 26"                       # cells & cells temps query
    ]},
    { "battery_num": 7, "cmds": [
        "D8 03 00 80 00 01 96 EB",                      # battery D8 (modbus ID #7) ping
        "D8 03 00 28 00 17 96 C5",                      # block information query
        "D8 03 00 00 00 27 16 D9"                       # cells & cells temps query
    ]},
    { "battery_num": 8, "cmds": [
        "D9 03 00 80 00 01 97 3A",                      # battery D9 (modbus ID #8) ping
        "D9 03 00 28 00 17 97 14",                      # block information query
        "D9 03 00 00 00 27 17 08"                       # cells & cells temps query
    ]}
]
