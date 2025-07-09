# modbus_battery.py

from modbus_gateway import modbus_crc16

def build_read_holding_registers_query(slave: int, register: int, count: int, modbus_registers) -> bytes:
    """
    Build a Modbus RTU read holding registers query with CRC16.
    """
    func = modbus_registers.FUNC_READ_HOLDING_REGS
    frame = bytes([slave, func]) + register.to_bytes(2, 'big') + count.to_bytes(2, 'big')
    return frame + modbus_crc16(frame)


def get_all_queries_for_battery(bat_id: int, modbus_registers) -> dict:
    """
    Return dictionary of queries to perform.
    The main program checks for presence of keys before sending queries,
    so you can comment out any query here to disable it safely.
    """

    if bat_id < 1 or bat_id > 15:
        raise ValueError("Battery ID must be between 1 and 15")

    return {
        'get_block_voltage':      build_read_holding_registers_query(bat_id, modbus_registers.REG_BLOCK_VOLTAGE, modbus_registers.LEN_BLOCK_VOLTAGE, modbus_registers),
        'get_cells_voltage':      build_read_holding_registers_query(bat_id, modbus_registers.REG_CELLS_VOLTAGE, modbus_registers.LEN_CELLS_VOLTAGE, modbus_registers),
        'get_temperature':        build_read_holding_registers_query(bat_id, modbus_registers.REG_TEMPERATURE, modbus_registers.LEN_TEMPERATURE, modbus_registers),
        'get_extra_temperature':  build_read_holding_registers_query(bat_id, modbus_registers.REG_EXTRA_TEMPERATURE, modbus_registers.LEN_EXTRA_TEMPERATURE, modbus_registers),
    }
