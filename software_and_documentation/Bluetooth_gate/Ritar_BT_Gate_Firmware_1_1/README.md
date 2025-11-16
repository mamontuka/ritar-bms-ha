# 📡 Ritar BT Gate Firmware

This repository contains the source code for the **Bluetooth Gate firmware for Ritar BMS**, designed for the **ESP32-S3-DEV-KIT-N8R8**.  

The firmware acts as a bridge between **Ritar RDAC Bluetooth batteries** and either the **Home Assistant Ritar-BMS Add-on** or the original **BluetoothLi** mobile app.

---

## 🚀 Key Features

- BLE connection to **Ritar master battery** via MAC address  
- Two operating modes:
  - **Native Mode (BluetoothLi App)**
  - **HA Mode (Home Assistant Add-on)**
- Built-in **Web Interface** with:
  - Wi-Fi setup (DHCP / Static)
  - Admin password configuration
  - Battery MAC configuration
  - OTA firmware updates
- Real-time logging via browser console
- Secure admin access
- Automatic battery reconnection
- OTA update support through Web UI

---

## 🧩 Source Structure

Main firmware file:

[FIRMWARE v1.1](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/Ritar_BT_Gate_Firmware_1_1.FACTORY.bin)

Major components inside the sketch:

- **Wi-Fi Manager**  
  Handles STA/AP mode, router connection, AP creation, reboots.

- **Web UI**  
  Simple HTML/JS admin panel + live console.

- **BLE Core**  
  - Scanning  
  - Connecting by MAC  
  - RDAC service handling  
  - Receiving packets  
  - Connection/disconnection/error events

- **Settings (NVS Storage)**  
  Stores Wi-Fi, admin password, battery MAC, operating mode.

- **OTA Update System**  
  Receives and writes firmware binary uploaded via Web UI.

- **Console / `slog()`**  
  Unified logging to UART and WebSocket.

---

## 🔧 Build Instructions

Use **Arduino IDE**

Required board settings:

Board: ESP32S3 Dev Module

Flash Size: 8MB (or more)

Partition Scheme: custom [partitions.csv](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/partitions.csv)


---

## 📲 Firmware Workflow

1. Boot → load saved configuration  
2. Connect to Wi-Fi or create AP  
3. Start Web Interface  
4. Initialize BLE  
5. If battery MAC is set → attempt to connect  
6. Based on selected mode:
   - Forward RDAC data to Home Assistant  
   - Or operate with BluetoothLi app  
7. Auto-reconnect when connection is lost

---

## 📄 License

Free to use within the Ritar-BMS / United BMS project.
