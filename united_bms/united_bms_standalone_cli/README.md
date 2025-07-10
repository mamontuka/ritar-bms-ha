**United BMS debugger/commandline tool**

**"--write" option USE AT OWN RISK ! THAT OPTION CAN DAMAGE YOUR EQUIPMENT !**

Require python modules - pyyaml, pyserial

Modbus registers map in **register_map.yaml** can be ajusted for any BMS what works over modbus, or setted another one by option:

        --map file_name.yaml

First use :

Be sure what .py file have execute rights for your user/group, if not - chmod 777 ./cli.py

python3 cli.py -h

    options:
      -h, --help            show this help message and exit
      --tcp TCP             TCP address like 192.168.0.100:50500
      --serial SERIAL       Serial port like /dev/ttyUSB0
      --slave SLAVE         Modbus slave ID (default: 1)
      --read READ           Register name or address to read
      --count COUNT         Number of registers to read (default: 1)
      --write WRITE         Write format: <register=value>
      --map MAP             YAML file with register name -> address map
      --mode {modbus_tcp,rtu_tcp,rtu_serial}
                        Modbus connection mode: rtu_tcp (default), or rtu_serial
      --timeout TIMEOUT     Connection timeout in seconds (default: 3)


How to Use

Read registers over RTU TCP (raw RTU frame over TCP):

    ./cli.py --tcp 192.168.0.100:50500 --slave 1 --read SOC --mode rtu_tcp

Read registers over Serial RTU:

    ./cli.py --serial /dev/ttyUSB0 --slave 1 --read SOC --mode rtu_serial

Write a value:

    ./cli.py --tcp 192.168.0.100:50500 --slave 1 --write SOC=85.0 --mode rtu_tcp


Example usage for get cells voltages :

    ./cli.py --tcp 192.168.0.100:50500 --slave 1 --read 40 --count 16 --slave 1 --mode rtu_tcp

Result output

    [READ] Register 40 values: [3370, 3410, 3396, 3410, 3418, 3393, 3428, 3403, 3408, 3373, 3417, 3398, 3414, 3380, 3420, 3420]

Example usage for get SOC, SOH, remain capacity, full capacity values :

    ./cli.py --tcp 192.168.0.100:50500 --slave 1 --read SOC --count 6 --slave 1 --mode rtu_tcp

    [READ] Register 2 values: [1000, 1000, 10000, 10000, 10000, 16]

"--count 6" option mean what we read 6 registers, with start from "SOC" (register 2) and end on "Battery_cycle_count" (register 7) (watch in register_map.yaml)

and for example :

    ./cli.py --tcp 192.168.0.100:50500 --slave 1 --read 1 --count 7 --slave 1 --mode rtu_tcp

    [READ] Register 1 values: [5448, 1000, 1000, 10000, 10000, 10000, 16]

mean what we read from 1st register (block voltage) to 7 (cycles) on "--slave 1" (battery number 1 by DIP switches)

