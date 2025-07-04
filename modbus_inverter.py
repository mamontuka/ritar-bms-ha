# modbus_inverter.py

import time
import json
import console_info

from modbus_registers import (
    REG_INVERTER_PROTOCOL,
    INVERTER_PROTOCOLS,
)

INVERTER_PROTOCOLS_REVERSE = {v: k for k, v in INVERTER_PROTOCOLS.items()}

def read_inverter_protocol(gateway, battery_id):
    regs = gateway.read_holding_registers(battery_id, REG_INVERTER_PROTOCOL, 1)
    if regs:
        return regs[0]
    return None

def write_inverter_protocol(gateway, battery_id, value, on_write=None):
    success = gateway.write_multiple_registers(battery_id, REG_INVERTER_PROTOCOL, [value])
    if success and on_write:
        on_write()
    return success

def read_all_inverter_protocols(client, gateway, battery_ids):
    results = []
    for bat in battery_ids:
        val = read_inverter_protocol(gateway, bat)
        results.append((bat, val, INVERTER_PROTOCOLS.get(val, "Unknown") if val is not None else "No protocol read"))
        time.sleep(0.5)
    return results

def publish_inverter_protocol(client, gateway, battery_ids, on_write=None):
    global pause_polling_until
    topic_cfg = "homeassistant/select/ritar_ess/inverter_protocol/config"
    topic_state = "homeassistant/select/ritar_ess/inverter_protocol/state"
    topic_cmd = "homeassistant/select/ritar_ess/inverter_protocol/set"

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

    client.publish(topic_cfg, json.dumps(cfg), retain=True)

    types = []
    for bat in battery_ids:
        val = read_inverter_protocol(gateway, bat)
        if val is not None:
            types.append(val)
        else:
            print(f"[WARN] No inverter protocol read from battery {bat}")
        time.sleep(0.5)

    if types:
        common = types[0]
        if all(t == common for t in types):
            client.publish(topic_state, json.dumps({"state": INVERTER_PROTOCOLS.get(common, "Unknown")}), retain=True)
        else:
            print("Mixed inverter protocols detected among batteries !!! SET INVERTER PROTOCOL IN MQTT **RITAR ESS** DEVICE !!!")
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
            pause_polling_until = time.time() + 7
            for bat in battery_ids:
                write_inverter_protocol(gateway, bat, value, on_write=on_write)
                time.sleep(2)
            client.publish(topic_state, json.dumps({"state": payload}), retain=True)

            print("[INFO] Please wait result confirmation...")
            updated_protocols = read_all_inverter_protocols(client, gateway, battery_ids)
            console_info.print_inverter_protocols_table_batteries(updated_protocols)
            print("[INFO] Next change available after 10 seconds !")
        else:
            print(f"[WARN] Unknown inverter protocol: {payload}")
        print("-" * 112)

    client.message_callback_add(topic_cmd, on_message)
    client.subscribe(topic_cmd)

    def refresh():
        types = []
        for bat in battery_ids:
            val = read_inverter_protocol(gateway, bat)
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
