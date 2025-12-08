#!/usr/bin/env python3
# client.py
# ESP Bluetooth BMS Reader for development purposes (WebSocket passthrough client)
#
# This script connects to an ESP device via WebSocket and sends low-level
# hex commands that query battery telemetry (block voltage, SOC, cycles,
# temperatures, cell voltages, etc.) over Bluetooth.
#
# Each battery has its own command set and is queried sequentially.
# The ESP forwards these commands to the BMS and sends back raw notifications.
#
# Features:
# - Multi-battery support (1..8)
# - Per-battery independent client instances
# - Full debug output (raw notify, block data, cell voltages, temps)
# - Blocking command/response model with event-based sync
# - Configurable timing for Bluetooth recovery between batteries
#
# Author: Oleh Mamont (C) 2025
# Version: 1.0
# ------------------------------------------------------------------------------

import time
import json
import sys
import threading
from websocket import WebSocketApp

# Ritar BT Gate API ("ws://ip_address:api_port/"):
ESP_WS_URL = "ws://192.168.5.21:50501/"

# ----------------------
# DEBUG FLAGS
# These define which diagnostic information is printed.
# ----------------------
DEBUG_SHOW_ALL = False              # Raw ESP logs + everything
DEBUG_SHOW_WRITE = False            # Outgoing written commands
DEBUG_SHOW_BYTES_DEC = False        # Show all byte pairs in decimal
DEBUG_SHOW_BLOCK = True             # Show parsed block-level values
DEBUG_SHOW_CELLS_VOLTAGES = True    # Show cell voltages
DEBUG_SHOW_TEMPS = True             # Show temperature readings

# ----------------------
# TIMINGS
# ----------------------
DELAY_BETWEEN_CMDS = 0.5            # Delay between commands for same battery
CMD_TIMEOUT = 2.0                   # Max wait per command response
POLL_INTERVAL = 15.0                # Delay between full cycles of all batteries
NEXT_BATTERY_DELAY = 3.0            # Time between finishing one battery and starting next

# ----------------------
# NUMBER OF BATTERIES (1..8)
# ----------------------
NUM_BATTERIES = 2

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

# Limit ACTIVE_BATTERIES based on NUM_BATTERIES
if NUM_BATTERIES < 1:
    NUM_BATTERIES = 1
elif NUM_BATTERIES > len(BATTERIES_CONFIG):
    NUM_BATTERIES = len(BATTERIES_CONFIG)

ACTIVE_BATTERIES = BATTERIES_CONFIG[:NUM_BATTERIES]

# ----------------------
# TEMPERATURE TABLE (RAW hex -> °C)
# Ritar encoding uses a shifted value; this table converts raw byte to °C.
# ----------------------
RAW_TO_C = {f"{0x3F + (c - 23):02X}": c for c in range(-20, 61)}

# ----------------------
# PARSERS
# ----------------------
def parse_block_notify(notify_hex: str):
    """
    Parse block-level frame:
    - Voltage
    - SOC
    - Cycles
    - MOS temperature
    - ENV temperature
    """
    parts = notify_hex.split()
    if len(parts) < 24:
        return None, None, None, None, None

    data = parts[3:]
    try:
        block_voltage = int(data[0] + data[1], 16) / 10.0

        # --- apply correction: add +0.1 V to match real voltage ---
        block_voltage += 0.0

        soc = int(data[4] + data[5], 16) / 10.0
        cycles = int(data[22] + data[23], 16)
        mos_t_raw = int(data[12] + data[13], 16)
        env_t_raw = int(data[13], 16)

        mos_t = RAW_TO_C.get(f"{mos_t_raw:02X}", 0)
        env_t = RAW_TO_C.get(f"{env_t_raw:02X}", 0)

    except Exception:
        return None, None, None, None, None

    return block_voltage, soc, cycles, mos_t, env_t


def parse_cells_notify(notify_hex: str):
    """
    Parse cell voltages (16 cells) and 4 temperature sensors.
    Also optionally prints decimal pairs if DEBUG_SHOW_BYTES_DEC is enabled.
    """
    parts = notify_hex.split()
    if len(parts) < 36:
        return [], [], []

    data_bytes = parts[3:]
    voltages = []

    # 16 voltages => 32 bytes
    for i in range(0, 32, 2):
        try:
            voltages.append(int(data_bytes[i] + data_bytes[i+1], 16))
        except Exception:
            voltages.append(0)

    # Parse 4 temperatures from bytes 64..71
    temps = []
    try:
        temp_bytes = data_bytes[64:72]
        for i in range(1, 8, 2):
            temps.append(RAW_TO_C.get(temp_bytes[i], 0))
    except Exception:
        temps = [0, 0, 0, 0]

    # Optional decimal-dump
    if DEBUG_SHOW_BYTES_DEC:
        print("[BYTES DECIMAL] pairs (CELLS):")
        for i in range(0, len(data_bytes)-1, 2):
            try:
                val = int(data_bytes[i] + data_bytes[i+1], 16)
                print(f"{data_bytes[i]} {data_bytes[i+1]} -> {val}")
            except Exception:
                pass

    return voltages, temps, data_bytes


# ----------------------
# CURRENT PARSER
# Ritar encodes current as difference from 30000.
# ----------------------
ZERO_CURRENT_RAW = 30000
CURRENT_SCALE = 0.1000

def parse_block_current(data_bytes):
    """
    Convert 2 bytes of "raw current" to real amps.
    Positive = charging, negative = discharging.
    """
    try:
        raw = int(data_bytes[2] + data_bytes[3], 16)
        return round((ZERO_CURRENT_RAW - raw) * CURRENT_SCALE, 2)
    except Exception:
        return None


# ----------------------
# CLIENT PER BATTERY
# ----------------------
class ESPBatteryClient:
    """
    Manages WebSocket connection per battery.
    Sends all commands, waits for responses, parses notify frames.
    """

    def __init__(self, url, battery_num, cmds):
        self.url = url
        self.battery_num = battery_num
        self.cmds = cmds

        self.ws = None
        self.lock = threading.Lock()

        self.current_cmd = None
        self.cmd_event = threading.Event()
        self.all_commands_done = threading.Event()

    def on_open(self, ws):
        print(f"[READING BATTERY {self.battery_num}] Connected")
        ws.send("set_mode python-driven")
        print("[WS] setting mode -> python-driven")

        # Launch sender in background thread
        threading.Thread(target=self.send_commands, args=(ws,), daemon=True).start()

    def send_commands(self, ws):
        """
        Sends all commands for this battery one-by-one,
        waits for confirmations using cmd_event,
        then closes the WebSocket.
        """
        print(f"[READING BATTERY {self.battery_num}] Connecting and sending commands...")
        print("-" * 125)

        for cmd in self.cmds:
            payload = json.dumps({"cmd": cmd})
            self.current_cmd = cmd
            self.cmd_event.clear()

            if DEBUG_SHOW_WRITE:
                print("[WRITE] ->", cmd)

            try:
                ws.send(payload)
                self.cmd_event.wait(timeout=CMD_TIMEOUT)
            except Exception as e:
                if DEBUG_SHOW_WRITE:
                    print("[WRITE ERROR]", e)

            time.sleep(DELAY_BETWEEN_CMDS)

        time.sleep(0.5)
        self.all_commands_done.set()
        ws.close()
        print("-" * 125)
        print(f"[READING BATTERY {self.battery_num}] Done sending commands")

    def on_message(self, ws, message):
        """
        Handle incoming notifications.
        Detect which command they belong to.
        Route to block or cell parser.
        """
        try:
            j = json.loads(message)
            notify = j.get("notify")
            if not notify:
                if DEBUG_SHOW_ALL:
                    print("[ESP LOG]", message)
                return
        except json.JSONDecodeError:
            if DEBUG_SHOW_ALL:
                print("[ESP LOG]", message)
            return

        with self.lock:
            if self.current_cmd and notify.startswith(self.current_cmd[:2]):
                self.cmd_event.set()

        parts = notify.split()
        third_byte = parts[2]

        if third_byte == "4E":
            # Cell notify
            voltages, temps, _ = parse_cells_notify(notify)

            if voltages and DEBUG_SHOW_CELLS_VOLTAGES:
                print(f"[BATTERY {self.battery_num} CELLS VOLTAGES]", voltages)

            if temps and DEBUG_SHOW_TEMPS:
                print(f"[BATTERY {self.battery_num} CELLS TEMPS]", temps)

        else:
            # Block notify
            block_v, soc, cycles, mos_t, env_t = parse_block_notify(notify)
            data_bytes = parts[3:]

            if DEBUG_SHOW_BYTES_DEC:
                print("[BYTES DECIMAL] pairs (BLOCK):")
                for i in range(0, len(data_bytes)-1, 2):
                    try:
                        val = int(data_bytes[i] + data_bytes[i+1], 16)
                        print(f"{data_bytes[i]} {data_bytes[i+1]} -> {val}")
                    except Exception:
                        pass

            # ENV temp offset (+2°C known sensor bias)
            if env_t is not None:
                env_t += 2

            current = parse_block_current(data_bytes)
            power = round(block_v * current) if (block_v is not None and current is not None) else None

            if block_v is not None and DEBUG_SHOW_BLOCK:
                info = (
                    f"[BATTERY {self.battery_num} BLOCK] "
                    f"voltage={block_v}V, SOC={soc}%, cycles={cycles}, "
                    f"MOS_T={mos_t}°C, ENV_T={env_t}°C"
                )
                if current is not None:
                    info += f", current={current}A"
                    if power is not None:
                        info += f", power={power}W"
                print(info)

    def on_error(self, ws, err):
        if DEBUG_SHOW_ALL:
            print(f"[WS ERROR BATTERY {self.battery_num}]", err)

    def on_close(self, ws, code, msg):
        if DEBUG_SHOW_ALL:
            print(f"[WS CLOSED BATTERY {self.battery_num}]", code, msg)

    def run_once(self):
        """
        Executes one full command cycle for this battery.
        """
        self.all_commands_done.clear()

        self.ws = WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

        t = threading.Thread(target=self.ws.run_forever, kwargs={"ping_interval": 10, "ping_timeout": 5})
        t.start()

        self.all_commands_done.wait()
        t.join()


# ----------------------
# MAIN LOOP
# ----------------------
if __name__ == "__main__":
    print(f"python-driven client -> talking to ESP passthrough ({NUM_BATTERIES} batteries)")

    clients = [
        ESPBatteryClient(ESP_WS_URL, cfg["battery_num"], cfg["cmds"])
        for cfg in ACTIVE_BATTERIES
    ]

    while True:
        for client in clients:
            client.run_once()
            time.sleep(NEXT_BATTERY_DELAY)

        print(f"[INFO] Waiting {POLL_INTERVAL}s before next battery read cycle...\n")
        time.sleep(POLL_INTERVAL)
