# CONNECTING WITH DEYE INVERTER OVER CAN BUS

In official manuals proposed to connect Ritar batteries over RS485 to Deye inverters, 
but in this case on ESS system with multi battery units we have troubles with modbus IDs, 
need offset inverter modbus ID after last battery ID on bus. </br>

In alternative undocumented connection over CAN bus, now we have profit with splitting modbus tree on 
two sides - on inverter side own modbus numeration, on batteries side - too. So ESS at now can have 16 battery units, 
be readable like was over RS485 to ethernet gate from HA integration, have connection to inverter over CAN protocol instead RS485, 
from inverter side - own RS485 modbus numeration - give ability to connect anotherone "RS485 to ethernet gate" for reading inverter(s), 
ability to build on this side splitted paralell inverters setup with unique modbus IDs. </br>

Also this alternative connection give more clear and improved work with batteries, better balancing units. **Recomended to use with more than one battery units atm.**</br>

__better battery units balancing provided with TURNED OFF float charge in inverter settings__ , with turned ON float charge - inverter do disbalance betwen battery units </br>

Master battery:

![screenshot](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/UNDOCUMENTED_WIRING_WITH_DEYE/1_MASTER_battery.jpg)

Slave battery(s):

![screenshot](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/UNDOCUMENTED_WIRING_WITH_DEYE/2_SLAVE_battery.jpg)

Settings in vendor service software:

![screenshot](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/UNDOCUMENTED_WIRING_WITH_DEYE/3_settings_for_batteries_over_vendor_software.jpg)

Patchcord scheme:

![screenshot](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/UNDOCUMENTED_WIRING_WITH_DEYE/4_patchcord_scheme.jpg)

Fast but dirty trick:

![screenshot](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/UNDOCUMENTED_WIRING_WITH_DEYE/5_patchcord_fast_cut_n_join_example.jpg)

Properly patchcord from inverter side:

![screenshot](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/UNDOCUMENTED_WIRING_WITH_DEYE/6_properly_patchcord_inverter_side.jpg)

Connection to Deye inverter:

![screenshot](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/UNDOCUMENTED_WIRING_WITH_DEYE/7_connection_to_inverter.jpg)

Setup CAN protocol mode (pylon_can) 00 :

![screenshot](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/UNDOCUMENTED_WIRING_WITH_DEYE/8_deye_CAN_lithium_mode_00.jpg)

Information output example :

![screenshot](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/UNDOCUMENTED_WIRING_WITH_DEYE/9_deye_test_lab_with_2_ritar_batteries_over%20_CAN.jpg)

