# Developer Reference — Standalone Ritar Bluetooth BMS Reader/Parser (`client.py`)

This document provides a complete developer-level technical reference for the ESP-based Bluetooth BMS WebSocket client used for reading telemetry from Ritar batteries.

**Version:** 1.0  
**Author:** Oleh Mamont © 2025

**Compatible with:** [Ritar BT Gate firmware ≥ 1.1](https://github.com/mamontuka/ritar-bms-ha/tree/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1)

---

## Technical limitations of the Ritar Bluetooth interface:

**The maximum number of batteries is 8 (D2-D9, Modbus ID from 1 to 8). 
Unit temperature and voltage display are roughly rounded. 
The registers used by the Bluetooth interface do not match those used by Modbus. 
I haven't yet found a way to write to these registers, but I might figure it out later.**

---

## 1. Overview

`client.py` is a Python tool for development and debugging of the Bluetooth passthrough interface implemented inside the ESP-based **Ritar BT Gate**.

It communicates with the ESP over **WebSocket**, sending low-level hex command frames that get forwarded to the BMS via Bluetooth.

The script supports:

- **1–8 independent batteries**, each with its own Bluetooth address and Modbus-like command set  
- **Sequential battery polling**  
- **Full debug output** of all parsed values  
- **Blocking command/response** model with event-based synchronization  
- Reliable parsing of **block-level and cell-level telemetry**  
- Conversion of **raw temperatures**, voltage, and current encodings  
- **Configurable timing** (delays, timeouts, poll intervals)

---

## 2. Architecture

```
Python client
    ↓ WebSocket JSON { "cmd": "XX YY ZZ ..." }
ESP Ritar BT Gate
    ↓ forwards raw bytes
Battery BMS (Bluetooth)
```

The ESP works in **passthrough mode**:

- Python sends commands as JSON objects  
- ESP forwards the raw byte payload to the battery  
- Battery answers with raw hex frames  
- ESP wraps the response in JSON: `{ "notify": "AA BB CC ..." }`  
- Python parses the data and prints decoded information  

---

## 3. Data Flow per Battery

```
set_mode python-driven
send command #1 → wait for notify #1
send command #2 → wait for notify #2
send command #3 → wait for notify #3
...
close connection
```

Each battery is handled by a separate instance of **ESPBatteryClient**.

---

## 4. Timing Model

| Setting               | Description                                         |
|----------------------|-----------------------------------------------------|
| `DELAY_BETWEEN_CMDS` | Time between commands for the same battery          |
| `CMD_TIMEOUT`        | Max wait for the answer to each command             |
| `NEXT_BATTERY_DELAY` | Pause between different batteries (Bluetooth reset) |
| `POLL_INTERVAL`      | Pause between full cycles of all batteries          |

This timing guarantees stable Bluetooth switching between BMS devices.

---

## 5. Multi-Battery Support

The script supports **1 to 8 batteries**.

```python
NUM_BATTERIES = 2
ACTIVE_BATTERIES = BATTERIES_CONFIG[:NUM_BATTERIES]
```

Each battery has:

- unique Modbus-like device ID (`D2`, `D3`, `D4`, …)
- unique command set (ping, block info, cell info)
- separate print/debug output

Batteries are queried in the order defined in `BATTERIES_CONFIG`.

---

## 6. Command Set Structure

Each battery defines:

### 1️⃣ Wakeup (only battery #1)
Used to activate the master battery, for others used ping query.

### 2️⃣ Ping  
Checks if battery number is alive and responsive.

### 3️⃣ Block Information  
Returns:

- block voltage  
- SOC  
- cycles  
- MOS temperature  
- ENV temperature  
- raw current data  

### 4️⃣ Cell Voltages & Temperature Sensors  
Contains:

- 16 cell voltages  
- 4 temperature sensors  

Example (battery #2):

```
"D3 03 00 00 00 27 17 A2"
```

---

## 7. Parsers

### 7.1 Block Parser (`parse_block_notify`)

Decodes:

- **Voltage** (0.1 V resolution)  
- **SOC** (0.1% resolution)  
- **Cycles**  
- **MOS temperature** (lookup table)  
- **ENV temperature** (lookup table)  
- **Current** (via special decoder)  
- **Power** = voltage × current  

Temperature lookup table:

```
RAW_TO_C = { "3F": -20, "40": -19, ..., "78": 60 }
```

---

### 7.2 Cell Parser (`parse_cells_notify`)

Extracts:

- 16 cell voltages (0.001 V scale)  
- 4 temperature values  
- optional decimal dump for debugging  

---

### 7.3 Current Parser

Ritar raw current encoding:

```
raw_current = big_endian_uint16
current(A) = (30000 - raw_current) × 0.1
```

Interpretation:

- Positive → **charging**  
- Negative → **discharging**

---

## 8. Debug System

Debug flags:

```python
DEBUG_SHOW_ALL
DEBUG_SHOW_WRITE
DEBUG_SHOW_BYTES_DEC
DEBUG_SHOW_BLOCK
DEBUG_SHOW_CELLS_VOLTAGES
DEBUG_SHOW_TEMPS
```

`DEBUG_SHOW_ALL = True` enables **full verbosity**.

---

## 9. WebSocket Layer

Each battery uses its **own WebSocket connection**.

Lifecycle:

```
on_open       → set_mode
send_commands → synchronized command execution
on_message    → parse notifies
on_close      → cleanup
```

Events:

- `cmd_event` — fires when expected notify arrives  
- `all_commands_done` — signals end of battery cycle  

Threading separates:

- WebSocket I/O  
- Command sending  
- Main loop  

Thread-safe access ensured with `self.lock`.

---

## 10. Main Loop

```python
while True:
    for battery in ACTIVE_BATTERIES:
        battery.run_once()
        time.sleep(NEXT_BATTERY_DELAY)

    sleep(POLL_INTERVAL)
```

This ensures:

- sequential battery scanning  
- controlled Bluetooth switching  
- stable timing behavior  
- continuous telemetry retrieval  

---

## 11. Extending the Script

### Add support for more batteries
Extend `BATTERIES_CONFIG`.

### Change timing parameters
Modify:

```
DELAY_BETWEEN_CMDS
CMD_TIMEOUT
NEXT_BATTERY_DELAY
POLL_INTERVAL
```

### Add new commands
Extend the command list in the per-battery configuration.

### Add export (MQTT, InfluxDB, HA)
Hook into parsed values inside `on_message`.

### Add logging
Wrap print statements with your logging framework.

---

## 12. Notes & Best Practices

- Battery #1 may require a wakeup packet  
- ESP Bluetooth may stall when switching devices → `NEXT_BATTERY_DELAY` fixes it  
- Use `NUM_BATTERIES` to limit count without modifying config  
- Threads keep the WebSocket reactive
- Bluetooth packets sometimes arrive out of order when the ESP is under load.
- For production, use longer poll intervals: **30–60 seconds**

---

## 13. License

This script is intended for development and diagnostics.  
All rights reserved © **Oleh Mamont**, 2025.

