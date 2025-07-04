### ritar-bms-ha
# <b>Homeassitant Addon for Ritar BAT-5KWH-51.2V BMS</b></br>

Supported **Ritar Power** 5, 10, 15KWH models, and maybe other, also have information about partial support **YHI Energy** and **Hollandia Power** batteries</br>

[RITAR POWER Site](https://www.gptess.com/lithium-ion_battery_System/66.html)\
[Official documentation](https://github.com/mamontuka/ritar-bms-ha/tree/main/official_documentation) \
[Official service software](https://github.com/mamontuka/ritar-bms-ha/tree/main/official_bms_software) \
[Official monitoring bluetooth android application](https://github.com/mamontuka/ritar-bms-ha/tree/main/android_bluetooth_monitoring_app) \
[Review pictures](https://github.com/mamontuka/ritar-bms-ha/tree/main/battery_review_pictures)

[RS485 to ethernet gate software and documentation](https://github.com/mamontuka/ritar-bms-ha/tree/main/RS-485_to_ethernet_gate)\
[Wiring to RS485 to ethernet gate](https://github.com/mamontuka/ritar-bms-ha/blob/main/RS-485_to_ethernet_gate/WIRING.md)\
[**CONNECT WITH DEYE INVERTERS OVER CAN BUS**](https://github.com/mamontuka/ritar-bms-ha/tree/main/UNDOCUMENTED_WIRING_WITH_DEYE/README.md)

[Unified Modbus BMS debugger/commandline tool](https://github.com/mamontuka/ritar-bms-ha/tree/main/Modbus_BMS_Debugger)\
[BMS protocol reverse engineering examples](https://github.com/mamontuka/ritar-bms-ha/tree/main/bms_protocol_reverse%20engineering)

[Homeassistant community page](https://community.home-assistant.io/t/ritar-bat-5kwh-51-2v-lifepo4-battery/)\
[Homeassitant entities cards examples](https://github.com/mamontuka/ritar-bms-ha/tree/main/homeassistant_entities_cards_examples)

[Screenshots](https://github.com/mamontuka/ritar-bms-ha/tree/main/homeassistant_entities_cards_examples/homeassistant_screenshots)

</br>\
Instalation : </br>\
1 - Add this repository to addons (three dots) - https://github.com/mamontuka/ritar-bms-ha </br>
2 - Install this addon </br>
3 - In addon setings choose RS485 gate IP, port, and how much battery you have (at now supported 1 - 15), MQTT settings </br>
4 - Take examples, ajust for self </br>
</br>
</br>

>UPDATE 1.9.4.1 - **HOTFIX** Fixed wrong measurement unit for x_pack_full_charge_voltage. Please delete in mqtt logic device Ritar ESS, and restart addon. It will repair wrong graphs.</br>

>UPDATE 1.9.4 - MAJOR UPDATE. Big amount code optimizations, structure reworks, fixes. Added new functional for read BMS EEPROM presets, what show in addon console log most important BMS parameters, in setups with more than one battery - check parameters betwen batteries, publish they into mqtt Ritar ESS device, for more information. In case if parameters different betwen batteries - draw tables for analyse to addon console log, remove EEPROM preset from Ritar ESS. **Keep in mind, what Homeassistant round values by default. Change Voltages round to 2 symbols, eg. 58.40, etc**</br>\
UPDATE 1.9.2.5 - **HOTFIX** Fixed in Ritar ESS - SOC Average and Voltage Average spikes on graphs. Structure improvements. </br>
UPDATE 1.9.2.4 - **HOTFIX** SETTED BACK DEFAULT read_timeout to **15 SECONDS**, because testing on my setup - 2x5.1 Rittar batteries (SMA protocol) what connected over CAN bus to Deye 6K-SG03LP1-EU (LiBMS protocol 00), show what with less than 15 sec read_timeout - CAUSE LOST CONNECTION WITH INVERTER, change this option by your opinion, but be awared about possible issues ! Different fixes in almost all code parts. Added switch into configuration, for turn on not critical warnings in console output (turned off by default).</br>\
UPDATE 1.9.2 - fixes, cleanups, improving addon log output, battery readings output to console now turnable from configuration and by default turned off. </br>\
UPDATE 1.9.1 - added option in "Ritar ESS" logic device, for set compatible inverter protocol on connected batteries units, directly from Homeassistant. Inverter protocols, supported by Ritar BMS listed below: </br>

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

>UPDATE 1.9 - MAJOR UPDATE. successfuly reworked protocol.py, reworked querries, reworked logic structures, fuses for prevent publication into MQTT/RecorderDB wrong or missreaded values, default read_timeout reduced to 10 seconds for better and fast response (set in config 10sec or less, if you see issues in addon log). Can work in realtime response with read_timeout 1 second (require more CPU resources). Ritar ESS logic device prepared for registers write functional in future releases. Zero DIP numbered battery no longer supported due protocol and modbus limitations, maximum amount of battery units - 15 at now. </br>\
UPDATE 1.8.12 - fixes </br>\
UPDATE 1.8.10 - added new MQTT device - **"Ritar ESS"**, what contain summary SOC, average batteries voltage, average MOS and environment temperatures, summary current and power sensors, for all present battery units. Several small fixes. Logic and parsing improvements, hotfixes. </br>\
UPDATE 1.8.8 - reworked modbus_gateway.py for compability with my brand new [**Unified Modbus BMS debugger/commandline tool**](https://github.com/mamontuka/ritar-bms-ha/tree/main/Modbus_BMS_Debugger), for development purposes and future releases. </br>\
UPDATE 1.8.7 - informational. [README HERE](https://github.com/mamontuka/ritar-bms-ha/tree/main/BMS_SETTINGS) </br>\
UPDATE 1.8.6 - cosmetic switch in configuration, for numbering cells from zero, like "cell_01, cell_02... cell_16" instead default naming like "cell_1, cell_2... cell_16" </br> \
UPDATE 1.8.4 - improved temperature checks before publishing into MQTT. default batteries read timeout changed to 15 seconds, for more responsive work. </br>\
UPDATE 1.8.2 - config.yaml hotfix, added uart:true, usb:true </br>\
UPDATE 1.8.1 - docker-compose.yaml hotfix, added devices /dev/ttyUSB0 and /dev/ttyUSB1 </br>\
UPDATE 1.8 - added support for serial connection, now you can choose what connection type you prefer. Major reworks and optimizations. </br>\
UPDATE 1.7.3 - added support for **up to 16 battery units. 15 - DIP switches 1111, 16 (zero number actualy) - DIP switches 0000.** Added important information about alternative wiring with Deye inverters over [**CAN bus - NEW UNDOCUMENTED IN OFFICIAL SOURCES WAY TO CONNECT WITH DEYE INVERTERS OVER CAN BUS**](https://github.com/mamontuka/ritar-bms-ha/tree/main/UNDOCUMENTED_WIRING_WITH_DEYE/README.md) </br>\
UPDATE 1.7.2 - added support for [**up to 14 battery units. READ THIS information about modbus IDs, DIP switches, inverter setup !**](https://github.com/mamontuka/ritar-bms-ha/blob/main/RS-485_to_ethernet_gate/WIRING.md) . Modbus IDs 0 and 15 - reserved for technical purposes. </br>\
UPDATE 1.7 - MAJOR UPDATE. Serious main code reworking and optimizations, for FUTURE adding support more than 4 batteries units. PLEASE DO CLEAN ADDON REINSTALL WITH DELETING ADDON DATA for properly work ! Sensors data in this case, will be PRESERVED and NOT loose. Sure - do IP, port, MQTT reconfigure how for clean installation.</br>\
UPDATE 1.6 - MAJOR UPDATE. API successfuly reworked, now all works over MQTT, not need anymore manual editting configuration.yaml (if you update from previous versions - remove in configuration.yaml all about Ritar batteries REST API ), all statistics from previous REST API sensors will be preserved and NOT disapear. Visit to this addon configuration, for setup MQTT. Restart Homeassistant for properly startup. Entities card examples you still can find by link below. </br>\
UPDATE 1.5 - added support for up to 4 batteries, more configurable queries delays, example templates updated. </br>\
UPDATE 1.4 - added WATTmeter charge/discharge power sensor, configurable RS485 connection timeout, configurable queries delay (usualy not need to be ajusted, but let it be), reworked voltage and SOC sensors API annoncement,  example templates updated. </br>\
UPDATE 1.3 - added Current charge/discharge Ampers sensor, example templates updated with new sensor. </br>\
UPDATE 1.2 - added MOS and Environment temperature sensors, major bugfixes, stability improvements, reading timeout set over config, example templates updated with new sensors. </br>\
UPDATE 1.1 - added cells temperature sensors 1-4 for batteries 1-2, example templates updated</br>
