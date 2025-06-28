# protocol.py

from modbus_gateway import modbus_crc16

# --- Register Maps ---
REG_BLOCK_VOLTAGE       = 0x0000
REG_CELLS_VOLTAGE       = 0x0028
REG_TEMPERATURE         = 0x0078
REG_EXTRA_TEMPERATURE   = 0x0091

LEN_BLOCK_VOLTAGE       = 0x10
LEN_CELLS_VOLTAGE       = 0x10
LEN_TEMPERATURE         = 0x04
LEN_EXTRA_TEMPERATURE   = 0x0A

# --- Function code ---
FUNC_READ_HOLDING_REGS = 0x03


def build_query(slave: int, register: int, count: int) -> bytes:
    """
    Build a Modbus RTU query with CRC16.
    """
    frame = bytes([slave, FUNC_READ_HOLDING_REGS]) + register.to_bytes(2, 'big') + count.to_bytes(2, 'big')
    return frame + modbus_crc16(frame)


def get_all_queries_for_battery(bat_id: int) -> dict:
    """
    Returns a dictionary of query names and bytes for a specific battery.
    bat_id: slave id, must be from 1 to 15 (no zero).
    """
    if bat_id < 1 or bat_id > 15:
        raise ValueError("Battery ID must be between 1 and 15")

    return {
        'get_block_voltage':      build_query(bat_id, REG_BLOCK_VOLTAGE, LEN_BLOCK_VOLTAGE),
        'get_cells_voltage':      build_query(bat_id, REG_CELLS_VOLTAGE, LEN_CELLS_VOLTAGE),
        'get_temperature':        build_query(bat_id, REG_TEMPERATURE, LEN_TEMPERATURE),
        'get_extra_temperature':  build_query(bat_id, REG_EXTRA_TEMPERATURE, LEN_EXTRA_TEMPERATURE),
    }
