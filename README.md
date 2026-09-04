# 🔋 Ritar BMS for Home Assistant
**A Home Assistant Addon for Ritar BAT-5KWH-51.2V BMS and compatible batteries**

---

**Current version: [2.0.7] 🧾  See [Update Details](https://github.com/mamontuka/ritar-bms-ha/blob/main/CHANGELOG.md) for full version history.**

---

## 🌐 Supported Devices

- ✅ Ritar Power 5KWH / 10KWH / 15KWH models
- ✅ Partial support: YHI Energy, Hollandia Power, [Predator](https://www.reddit.com/r/SolarDIY/comments/1lbz5dk/inside_a_ritar_xplfp48v100ah_predator/)
- ✅ Others via [United BMS](https://github.com/mamontuka/ritar-bms-ha/blob/main/united_bms/united_bms_modules/README.md)
- ✅ Supported **RS485-ethernet**, **serial**, **bluetooth** connection types

> ⚠️ For Bluetooth connection, a dedicated device and the appropriate firmware are required.  
> Documentation: [Ritar BT Gate](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/README.md)  
> ⚠️ Max 8 batteries (D2-D9, Modbus ID 1–8). Unit voltage/temperature is roughly rounded. Writing to Bluetooth registers is not yet supported.  
> ⚠️ In Bluetooth mode, reading/writing inverter protocol and battery presets is **disabled** due to Bluetooth limitations.  
> ⚠️ For accurate metrics, prefer **RS485 Ethernet Gate** or **serial** connection.

---

## 📷 Visual & Documentation

- [📄 RITAR POWER Site](https://www.gptess.com/lithium-ion_battery_System/66.html)
- [📄 Official Documentation](https://github.com/mamontuka/ritar-bms-ha/tree/main/software_and_documentation/Ritar_official_software_and_documentation/documentation)
- [🔧 Official Ritar BMS Software](https://github.com/mamontuka/ritar-bms-ha/tree/main/software_and_documentation/Ritar_official_software_and_documentation/software/windows)
- [📱 Official Android Bluetooth App](https://github.com/mamontuka/ritar-bms-ha/tree/main/software_and_documentation/Ritar_official_software_and_documentation/software/android)
- [🖼 Battery Review Pictures](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Ritar_official_software_and_documentation/review_pictures/README.md)

---

- [🔌 RS485 Adapters and Ethernet Gates Software and Documentation](https://github.com/mamontuka/ritar-bms-ha/tree/main/software_and_documentation/RS485_adapters_and_ethernet_gates)
- [🔌 Wiring to RS485 Basics, example equipment - Deye 6K-SG03LP1-EU + VKmodule ENET-485 gate](https://github.com/mamontuka/ritar-bms-ha/tree/main/software_and_documentation/RS485_adapters_and_ethernet_gates/VKmodule.com.ua_Enet-485/README.md)
- [🔌 Wiring with Deye Inverters Over CAN Bus](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/UNDOCUMENTED_WIRING_WITH_DEYE/README.md)
- [📱 Bluetooth Gate Firmware README (users)](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/firmware/README.md)
- [📱 Bluetooth Gate Firmware README (developers)](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/Ritar_BT_Gate_Firmware_1_1/README.md)
- [📱 Bluetooth Standalone reader/parser README (developers)](https://github.com/mamontuka/ritar-bms-ha/tree/main/software_and_documentation/Bluetooth_gate/developer_BT_client)

---

- [📊 Home Assistant Screenshots](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Homeassistant/homeassistant_screenshots/README.md)
- [📊 Home Assistant Cards Examples](https://github.com/mamontuka/ritar-bms-ha/tree/main/software_and_documentation/Homeassistant/homeassistant_cards)
---

- [💬 Community Page](https://community.home-assistant.io/t/ritar-bat-5kwh-51-2v-lifepo4-battery/)

---

## 🔧 Installation

1. Add this repo to **Home Assistant Add-on Store**  
   📍 `https://github.com/mamontuka/ritar-bms-ha`
2. Install the **Ritar BMS Addon**
3. Open Addon settings:
   - Set your RS485 Ethernet Gateway IP/Port
   - Define how many batteries (1–15)
   - Set your MQTT broker info
4. Restart addon
5. Enjoy automatically discovered sensors in Home Assistant!

---

## 🧩 United BMS Framework

Create **your own BMS addon** for other manufacturers  
🔗 [Read More about United BMS](https://github.com/mamontuka/ritar-bms-ha/blob/main/united_bms/README.md)

- [🔋 Supported Batteries](https://github.com/mamontuka/ritar-bms-ha/blob/main/united_bms/united_bms_modules/README.md)
- [🧰 Embedded United BMS Debugger/CLI](https://github.com/mamontuka/ritar-bms-ha/blob/main/united_bms/united_bms_ssh_cli/README.md)
- [🧰 Standalone version of United BMS Debugger/CLI](https://github.com/mamontuka/ritar-bms-ha/tree/main/united_bms/united_bms_standalone_cli)

---

- [💬 Community Page](https://community.home-assistant.io/t/united-bms-framework/)

---

## ⚙️ Features

- 🔁 RS485 & Serial Communication
- 📦 Up to **15 battery** unit support (with **RS485-ethernet** or **serial** connection type)
- 🌡 MOS/Environment/Cell temperatures
- 🔋 SOC, Block Voltage, Current, Power
- 📉 Graph filtering, spike protection
- 🧠 EEPROM preset analysis & alerts
- 🧪 Unified Modbus debugger CLI
- 📢 MQTT Discovery + HA Integration
- 🛠 United BMS Framework for custom BMS logic

---

## 🛠 Compatible Inverter Protocols

This addon supports setting inverter protocols via Home Assistant UI:

| Code | Protocol |
|------|----------|
| 0  | RITAR_RS485 (RITARV1_8) |
| 1  | DEYE_RS485 (Deye BMS Protocol 12), PLY(DEYE,SMK,FIRMAN,Hollandia) |
| 2  | GROWATT_RS485 |
| 3  | VOLTRONIC_RS485, LIB05(VOLTRONIC,XUNZEL,TESLA,GSB SOLAR,PCE) |
| 4  | UPOWER_RS485 |
| 5  | VERTIV_RS485 |
| 6  | ELTEK_RS485 |
| 7  | RITAR_MODBUSV1_9_RS485 |
| 8  | VICTRON_CAN |
| 9  | RITAR_CAN |
| 10 | SMA_CAN (Deye Protocol 00) |
| 11 | MEGAREVO_CAN |
| 12 | TBB_CAN |
| 13 | SOLIS_CAN |
| 14 | INHENERGY_RS485 |
| 15 | MUST_CAN |
| 16 | PYON_CAN |
| 17 | LUXPOWERTEK_RS485 |
| 18 | PHOCOS_RS485 |

---
