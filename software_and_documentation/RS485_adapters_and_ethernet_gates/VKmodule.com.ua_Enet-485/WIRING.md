# RS485 to ethernet gate wiring

RS485 gate wired to battery number 1, by BROWN PAIR (BROWN=B, WHITE-BROWN=A), to LINE IN battery hole (RJ45 7pin=WHITE-BROWN, 8pin=BROWN), LINE OUT port of battery number 1 wired by regular patchcord to battery number 2 LINE IN, RS485 port on battery number 1, wired to Deye 6K-SG03LP1 inverter port RS485/CAN, by regular patchcord </br>

Deye inverter works with Lithium battery protocol number 12 </br>
On inverter DIP switches - both DOWN, in advanced settings - mode - SLAVE, MODBUS SN is 16, because batteries IDs from 1 to 15 </br>

**Thats usable for less battery units too, from 1 up to 15 units. Inverter modbus ID must be higher than last battery ID !** </br>

![Batteries DIP switches](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/VKmodule.com.ua_Enet-485/DIP_Switches.jpg) </br>

Inverter DIP switches
![Deye Inverter DIP switches](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/VKmodule.com.ua_Enet-485/Inverter_DIP_Switches.jpg) </br>

![Inverter_MODBUS_ID](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/RS485_adapters_and_ethernet_gates/VKmodule.com.ua_Enet-485/Inverter_MODBUS_ID.jpg) </br>


