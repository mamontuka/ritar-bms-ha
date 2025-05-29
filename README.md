# ritar-bms-ha
# <b>Homeassitant Addon for Ritar BAT-5KWH-51.2V BMS</b></br>

Supported 5, 10, 15KWH models</br>

https://www.gptess.com/lithium-ion_battery_System/66.html

<b>Wiring to RS485 to ethernet gate<b> https://github.com/mamontuka/ritar-bms-ha/blob/main/RS-485_to_ethernet_gate/WIRING.md </br>

** NEW UNDOCUMENTED IN OFFICIAL SOURCES WAY TO CONNECT WITH DEYE INVERTERS OVER CAN BUS**
https://github.com/mamontuka/ritar-bms-ha/tree/main/UNDOCUMENTED_WIRING_WITH_DEYE/README.md

RS485 to ethernet gate software and documentation : https://github.com/mamontuka/ritar-bms-ha/tree/main/RS-485_to_ethernet_gate </br>

Official monitoring bluetooth android application : https://github.com/mamontuka/ritar-bms-ha/tree/main/android_bluetooth_monitoring_app </br>
Official service software : https://github.com/mamontuka/ritar-bms-ha/tree/main/official_bms_software </br>
Official documentation : https://github.com/mamontuka/ritar-bms-ha/tree/main/official_documentation </br>
Review pictures : https://github.com/mamontuka/ritar-bms-ha/tree/main/battery_review_pictures </br>

BMS protocol reverse engineering examples : https://github.com/mamontuka/ritar-bms-ha/tree/main/bms_protocol_reverse%20engineering </br>


Instalation : </br>
1 - Add this repository to addons (three dots) - https://github.com/mamontuka/ritar-bms-ha </br>
2 - Install this addon </br>
3 - In addon setings choose RS485 gate IP, port, and how much battery you have (at now supported 1 - 16), MQTT settings </br>
4 - Take examples below, ajust for self </br>

UPDATE 1.1 - added cells temperature sensors 1-4 for batteries 1-2, example templates updated</br>
UPDATE 1.2 - added MOS and Environment temperature sensors, major bugfixes, stability improvements, reading timeout set over config, example templates updated with new sensors. </br>
UPDATE 1.3 - added Current charge/discharge Ampers sensor, example templates updated with new sensor. </br>
UPDATE 1.4 - added WATTmeter charge/discharge power sensor, configurable RS485 connection timeout, configurable queries delay (usualy not need to be ajusted, but let it be), reworked voltage and SOC sensors API annoncement,  example templates updated. </br>
UPDATE 1.5 - added support for up to 4 batteries, more configurable queries delays, example templates updated. </br>
UPDATE 1.6 - MAJOR UPDATE. API successfuly reworked, now all works over MQTT, not need anymore manual editting configuration.yaml (if you update from previous versions - remove in configuration.yaml all about Ritar batteries REST API ), all statistics from previous REST API sensors will be preserved and NOT disapear. Visit to this addon configuration, for setup MQTT. Restart Homeassistant for properly startup. Entities card examples you still can find by link below. </br>
UPDATE 1.7 - MAJOR UPDATE. Serious main code reworking and optimizations, for FUTURE adding support more than 4 batteries units. PLEASE DO CLEAN ADDON REINSTALL WITH DELETING ADDON DATA for properly work ! Sensors data in this case, will be PRESERVED and NOT loose. Sure - do IP, port, MQTT reconfigure how for clean installation.</br>
UPDATE 1.7.2 - added support for **up to 14 battery units. READ THIS information about modbus IDs, DIP switches, inverter setup !** - https://github.com/mamontuka/ritar-bms-ha/blob/main/RS-485_to_ethernet_gate/WIRING.md . Modbus IDs 0 and 15 - reserved for technical purposes. </br>
UPDATE 1.7.3 - added support for **up to 16 battery units. 15 - DIP switches 1111, 16 (zero number actualy) - DIP switches 0000.** Added important information about alternative wiring with Deye inverters over **CAN bus - NEW UNDOCUMENTED IN OFFICIAL SOURCES WAY TO CONNECT WITH DEYE INVERTERS OVER CAN BUS**
https://github.com/mamontuka/ritar-bms-ha/tree/main/UNDOCUMENTED_WIRING_WITH_DEYE/README.md </br>
.</br>
UPDATE 1.8 - added support for serial connection, now you can choose what connection type you prefer. Major reworks and optimizations. </br>
UPDATE 1.8.1 - docker-compose.yaml hotfix, added devices /dev/ttyUSB0 and /dev/ttyUSB1 </br>
UPDATE 1.8.2 - config.yaml hotfix, added uart:true, usb:true </br>

Homeassitant entities cards examples : https://github.com/mamontuka/ritar-bms-ha/tree/main/homeassistant_entities_cards_examples </br>

