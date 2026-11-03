1. Copy override files into **/config/united_bms/** folder on homeassistant host
```
    /config/united_bms/main_settings.py
    /config/united_bms/parser_battery.py
```

2. Open up Ritar BMS Addon settings in text edit mode, put into text config window content from [This file](https://github.com/mamontuka/ritar-bms-ha/blob/main/united_bms/united_bms_modules/Ritar_LFP12_8V100AH_(G24)_G3_(BT)/addon_text_config.yaml) :

```
    connection_type: ethernet
    rs485gate_ip: 192.168.0.100
    rs485gate_port: 50500
    serial_port: /dev/ttyUSB0
    serial_baudrate: 9600
    connection_timeout: 3
    queries_delay: 0.2
    next_battery_delay: 1
    separate_battery_reading: true
    enable_modbus_inverter: false
    enable_modbus_eeprom: false
    bluetooth_gate_ip: 192.168.0.101
    bluetooth_gate_port: 50501
    bluetooth_delay_between_query: 0.5
    bluetooth_answer_wait_timeout: 2
    bluetooth_next_battery_delay: 3
    battery_model: United BMS Custom
    num_batteries: 1
    num_cells: 4
    read_timeout: 15
    console_output_enabled: true
    zero_pad_cells: false
    mqtt_broker: core-mosquitto
    mqtt_port: 1883
    mqtt_username: rodion
    mqtt_password: rodion098123
    warnings_enabled: false
    enable_debug_shell: false
```

3. Adjust configuration settings
4. Restart Ritar BMS Addon
