Example query hacks for battery 1 and battery 2 <br />
Battery 1 DIP switches 1000 <br />
Battery 2 DIP switches 0100 <br />

Im hope you will understand how to get query hacks for another batteries numbers,  <br />
if need more than two what already done by me  <br />

watch pictures here, with logic explanation  <br />

Battery SOC, pack voltage, pack capacity, cycle count :  <br />

For number 1 : <br />

RAW HEX:  <br />
01 03 00 00 00 10 44 06 <br />

same in python code : <br />
variable_name = b'\x01\x03\x00\x00\x00\x10\x44\x06'

same query for battery number 2 : <br />

RAW HEX:  <br />

02 03 00 00 00 10 44 35 <br />

in python code : <br />

variable_name = b'\x02\x03\x00\x00\x00\x10\x44\x35' <br />

Hacks for getting cells voltages:  <br />

bat 1 raw HEX : <br />
01 03 00 28 00 10 c4 0e <br />

bat 2 raw HEX: 
02 03 00 28 00 10 c4 3d <br />

bat 1 in python:
bat_1_get_cells_voltage = b'\x01\x03\x00\x28\x00\x10\xc4\x0e' <br />

bat 2 in python:
bat_2_get_cells_voltage = b'\x02\x03\x00\x28\x00\x10\xc4\x3d' <br />
