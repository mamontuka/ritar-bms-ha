# 📋 Changelog

All notable changes to the Ritar BMS Home Assistant Addon are documented here.

---

## [1.9.7.6]
Cleanup and rework repository structure, readme files and docs.

## [1.9.7.5]
Improvements and fixes for introduced **United BMS framework**. Updated logic, fallbacks, now `modbus_battery.py` module also available for custom modification. Feature marked stable, if you use **properly structured** modules templates. Also added protection from zero size modules.

## [1.9.7]
Introducing new feature - **United BMS** - this feature gives you the ability to customize Ritar BMS addon or create your own BMS addon for batteries manufactured by other vendors! [README](https://github.com/mamontuka/ritar-bms-ha/blob/main/united_bms/README.md). After update do double addon restart, or just reinstall, for properly changing work structure.

## [1.9.6]
Structure rework, code cleanups. Preparing for changing version numeration from "current" to "stable". At this moment, during tests, not found any issues, if you know what works not properly or not how expected - let me know, please.

## [1.9.5.6]
Structure rework for better source code understanding. Fixed properly forgotten config option `zero_pad_cells` - now it works as expected and switches cell numeration with cleanup in MQTT entities. Improved graphs spikes filtering in Ritar ESS device for multi-battery setups.

## [1.9.5]
Code cleanups, optimizations, structure reworks. Fixed wrong understanding by Home Assistant MQTT, EEPROM parameter `x_soc_alarm_threshold`, now shown correctly.

## [1.9.4.1] - HOTFIX
Fixed wrong measurement unit for `x_pack_full_charge_voltage`. Please delete MQTT logic device "Ritar ESS", and restart addon. It will repair wrong graphs.  
**AND/OR delete entity misvalues graphs** – [HOWTO](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Homeassistant/homeassistant_screenshots/delete_entity_missvalues_graphs.jpg)

## [1.9.4]
**MAJOR UPDATE**. Big amount of code optimizations, structure reworks, fixes.  
Added new functional for reading BMS EEPROM presets, which shows in addon console log most important BMS parameters.  
In setups with more than one battery - checks parameters between batteries, publishes them into MQTT Ritar ESS device for further information.  
If parameters differ - draw comparison tables in console and remove EEPROM preset from Ritar ESS.  
**Note:** Home Assistant rounds values by default — change voltage round to 2 digits, e.g. 58.40.

## [1.9.2.5] - HOTFIX
Fixed in Ritar ESS – SOC Average and Voltage Average spikes on graphs. Structure improvements.

## [1.9.2.4] - HOTFIX
Set back default `read_timeout` to **15 SECONDS** due to lost connection issue with Deye inverter using CAN.  
Fixes across multiple code parts.  
Added configuration switch to enable non-critical warnings (off by default).

## [1.9.2]
Fixes, cleanups, improved addon log output.  
Battery readings output to console now toggleable from configuration (default: off).

## [1.9.1]
Added protocol selector directly from Home Assistant for "Ritar ESS" logic device.  
Supported inverter protocols:

    0: "RITAR_RS485 (RITARV1_8)"
    1: "DEYE_RS485 (Deye BMS Protocol 12), PLY(DEYE,SMK,FIRMAN,Hollandia)"
    2: "GROWATT_RS485"
    3: "VOLTRONIC_RS485, LIB05(VOLTRONIC,XUNZEL,TESLA,GSB SOLAR,PCE)"
    4: "UPOWER_RS485"
    5: "VERTIV_RS485"
    6: "ELTEK_RS485"
    7: "RITAR_MODBUSV1_9_RS485"
    8: "VICTRON_CAN"
    9: "RITAR_CAN"
    10: "SMA_CAN (Deye BMS Protocol 00)"
    11: "MEGAREVO_CAN"
    12: "TBB_CAN"
    13: "SOLIS_CAN"
    14: "INHENERGY_RS485"
    15: "MUST_CAN"
    16: "PYON_CAN"
    17: "LUXPOWERTEK_RS485"
    18: "PHOCOS_RS485"


## [1.9]
**MAJOR UPDATE**.  
Reworked `protocol.py`, refined queries, added logic protections from invalid values reaching MQTT.  
Reduced default `read_timeout` to 10s. Can operate in real-time with 1s timeout (more CPU required).  
"Ritar ESS" logic prepared for future writable registers.  
**Battery ID 0 no longer supported**, max: 15 batteries.

## [1.8.12]
Minor fixes.

## [1.8.10]
New MQTT device **Ritar ESS** with:
- Summary SOC
- Average battery voltage
- Average temperatures (MOS/env)
- Summary current and power sensors

Also includes general logic and parsing fixes.

## [1.8.8]
Refactored `modbus_gateway.py` for compatibility with [United BMS Debugger/CLI](https://github.com/mamontuka/ritar-bms-ha/tree/main/united_bms/united_bms_standalone_cli)

## [1.8.7]
Informational. See [BMS Settings README](https://github.com/mamontuka/ritar-bms-ha/tree/main/software_and_documentation/Miscellaneous/BMS_SETTINGS)

## [1.8.6]
Added config option to enable zero-padded cell numbering (`cell_01`, `cell_02`, ...)

## [1.8.4]
Improved temperature filtering before MQTT publish.  
Changed default read timeout to 15 seconds.

## [1.8.2]
Config hotfix – added `uart: true` and `usb: true`.

## [1.8.1]
Docker hotfix – included `/dev/ttyUSB0` and `/dev/ttyUSB1`.

## [1.8]
**MAJOR UPDATE** – serial connection support.  
Refactoring and performance improvements.

## [1.7.3]
Added support for up to 16 batteries (IDs 1–15).  
Added [CAN-BUS wiring method with Deye inverters](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/UNDOCUMENTED_WIRING_WITH_DEYE/README.md)

## [1.7.2]
Support for up to 14 batteries.  
[Important Modbus & DIP info](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/VKmodule.com.ua_Enet-485/WIRING.md)

## [1.7]
**MAJOR UPDATE** – Refactor for large setups.  
**Please reinstall addon with data wipe.**

## [1.6]
**MAJOR UPDATE** – moved fully to MQTT.  
No more `configuration.yaml` edits required.  
Restart Home Assistant after setup.

## [1.5]
Support for up to 4 batteries.  
More config options and improved templates.

## [1.4]
- Added WATTmeter (charge/discharge power)
- RS485 timeout and delay options
- Improved SOC/Voltage MQTT announcement
- Updated example templates

## [1.3]
- Added Current sensor (Amps)
- Updated templates

## [1.2]
- Added MOS & Env temperature sensors
- Stability fixes, improved config
- Updated templates

## [1.1]
- Added cell temperature sensors 1–4 for batteries 1–2
- Updated example templates

