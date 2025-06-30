# inverter_protocol.py

import time
import json
from modbus_gateway import modbus_crc16

INVERTER_PROTOCOLS = {
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
}
INVERTER_PROTOCOLS_REVERSE = {v: k for k, v in INVERTER_PROTOCOLS.items()}

REG_INVERTER_PROTOCOL = 0x0020
FUNC_READ_HOLDING_REGS = 0x03
FUNC_WRITE_MULTIPLE_REGS = 0x10

def build_read_query(slave: int, register: int, count: int) -> bytes:
    frame = bytes([slave, FUNC_READ_HOLDING_REGS]) + register.to_bytes(2, 'big') + count.to_bytes(2, 'big')
    crc = modbus_crc16(frame)
    full_frame = frame + crc
    return full_frame

def build_write_multiple_registers(slave: int, register: int, values: list[int]) -> bytes:
    count = len(values)
    byte_count = count * 2
    frame = bytearray()
    frame.append(slave)
    frame.append(FUNC_WRITE_MULTIPLE_REGS)
    frame += register.to_bytes(2, 'big')
    frame += count.to_bytes(2, 'big')
    frame.append(byte_count)
    for v in values:
        frame += v.to_bytes(2, 'big')
    crc = modbus_crc16(frame)
    full_frame = bytes(frame) + crc
    return full_frame

def publish_inverter_protocol(client, gateway, battery_ids, on_write=None):
    global pause_polling_until
    topic_cfg = "homeassistant/select/ritar_ess/inverter_protocol/config"
    topic_state = "homeassistant/select/ritar_ess/inverter_protocol/state"
    topic_cmd = "homeassistant/select/ritar_ess/inverter_protocol/set"

    def read_inverter_protocol(bat_id):
        try:
            query = build_read_query(bat_id, REG_INVERTER_PROTOCOL, 1)
            gateway.send(query)
            resp = gateway.recv(7)
            if resp and len(resp) == 7 and resp[1] == FUNC_READ_HOLDING_REGS:
                value = int.from_bytes(resp[3:5], 'big')
                print(f"Current inverter protocol for battery {bat_id}: {INVERTER_PROTOCOLS.get(value, 'Unknown')} ({value})")
                return value
        except Exception as e:
            print(f"[WARN] Read inverter protocol failed for battery {bat_id}: {e}")
        return None

    def write_inverter_protocol(bat_id, value):
        try:
            query = build_write_multiple_registers(bat_id, REG_INVERTER_PROTOCOL, [value])
            gateway.send(query)
            resp = gateway.recv(8)
            if not resp or len(resp) != 8 or resp[1] != FUNC_WRITE_MULTIPLE_REGS:
                raise Exception("Invalid write response")
            print(f"[INFO] Set inverter protocol {value} to battery {bat_id}")
            if on_write:
                on_write()
        except Exception as e:
            print(f"[WARN] Write inverter protocol failed for battery {bat_id}: {e}")

    cfg = {
        "name": "Inverter Protocol",
        "command_topic": topic_cmd,
        "state_topic": topic_state,
        "unique_id": "inverter_protocol",
        "object_id": "inverter_protocol",
        "options": list(INVERTER_PROTOCOLS.values()),
        "value_template": "{{ value_json.state }}",
        "device": {
            "identifiers": ["ritar_ess"],
            "name": "Ritar ESS",
            "model": "Energy Storage System",
            "manufacturer": "Ritar"
        }
    }

    print("Ritar ESS ..")
    print(".")
    client.publish(topic_cfg, json.dumps(cfg), retain=True)

    types = []
    print("Reading inverter protocol from each battery..")
    print(".")
    for bat in battery_ids:
        val = read_inverter_protocol(bat)
        if val is not None:
            types.append(val)
        else:
            print(f"[WARN] No inverter protocol read from battery {bat}")
        time.sleep(0.5)

    if types:
        common = types[0]
        if all(t == common for t in types):
            print(".")
            print(f"Common inverter protocol for all batteries: {INVERTER_PROTOCOLS.get(common, 'Unknown')} ({common})")
            print(".")
            client.publish(topic_state, json.dumps({"state": INVERTER_PROTOCOLS.get(common, "Unknown")}), retain=True)
        else:
            print(".")
            print("Mixed inverter protocols detected among batteries !!! SET INVERTER PROTOCOL IN MQTT **RITAR ESS** DEVICE !!!")
            print(".")
            client.publish(topic_state, json.dumps({"state": "Unknown"}), retain=True)
    else:
        print("[WARN] No inverter protocols read from any batteries")
        client.publish(topic_state, json.dumps({"state": "Unknown"}), retain=True)

    def on_message(client, userdata, msg):
        global pause_polling_until
        payload = msg.payload.decode().strip()
        value = INVERTER_PROTOCOLS_REVERSE.get(payload)
        if value is not None:
            print(f"[MQTT] Changing inverter protocol to: {payload} ({value})")
            # Pause polling for 10 seconds
            pause_polling_until = time.time() + 10
            for bat in battery_ids:
                write_inverter_protocol(bat, value)
                
                # delay between writes
                time.sleep(0.5)
                
            client.publish(topic_state, json.dumps({"state": payload}), retain=True)
            
            # Reset pause
            pause_polling_until = 0
        else:
            print(f"[WARN] Unknown inverter protocol: {payload}")
        print("-" * 112)

    client.message_callback_add(topic_cmd, on_message)
    client.subscribe(topic_cmd)

    def refresh():
        types = []
        for bat in battery_ids:
            val = read_inverter_protocol(bat)
            if val is not None:
                types.append(val)
            time.sleep(0.5)
        if types:
            common = types[0]
            if all(t == common for t in types):
                client.publish(topic_state, json.dumps({"state": INVERTER_PROTOCOLS.get(common, "Unknown")}), retain=True)
            else:
                client.publish(topic_state, json.dumps({"state": "Unknown"}), retain=True)
        else:
            client.publish(topic_state, json.dumps({"state": "Unknown"}), retain=True)

    return refresh
