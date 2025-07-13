# Embedded United BMS Shell Interface

This shell utility is part of the **United BMS Framework**, providing a convenient and interactive CLI tool for configuring and reading data from RS485-connected BMS devices directly within a Home Assistant add-on environment.

---

### Usage Screenshots: [HERE](https://github.com/mamontuka/ritar-bms-ha/blob/main/united_bms/united_bms_ssh_cli/debugger_screenshots/README.md) 

---

## 🚪 How to Access the Shell

The United BMS shell runs **inside the add-on container** and is accessible via SSH.

### ✅ Enable Shell Access

1. Go to **Home Assistant > Settings > Add-ons > Ritar BMS**.
2. Open the **Configuration** tab.
3. Enable the following option:

```yaml
enable_shell: true
```

4. Save and restart the add-on.

### 🔐 Connect via SSH Client

Use any SSH client (e.g. `ssh`, PuTTY, MobaXterm) and connect to your Home Assistant host:

```bash
ssh debug@<HOME_ASSISTANT_IP> -p <EXPOSED_PORT>
```

- **Username:** `debug`
- **Password:** `debug` (can be changed in the shell)
- **Port:** must be mapped in your add-on or container settings

---

## 🧠 First-Time Configuration

After connecting via SSH, you’ll enter the interactive United BMS shell.

### 1. Configure your BMS connection:

```bash
united-bms> config debug
```

You will be prompted to:

- Select connection type: `tcp` or `serial`
- Enter connection details (e.g., `192.168.0.100:50500` or `/dev/ttyUSB0`)
- Specify how many BMS batteries (slaves) are connected

The configuration will be saved and automatically reused next time.

---

## 🧪 Reading Data from Your BMS

Once configured, you can read data from a connected BMS:

```bash
united-bms> read 1 soc 16
```

Where:

- `1` is the slave address (battery number)
- `soc` is the name of the register (defined in `register_map.yaml`)
- `16` is how many registers to read

You can also use raw register numbers:

```bash
united-bms> read 1 2 16
```

---

## 📁 Customization and Overrides

The shell interacts with a folder on your **Home Assistant host**:

```
/config/united_bms/
```

This directory is used to store:

- Your **custom override files** (`.yaml`, `.py`)
- A `register_map.yaml` file that maps **friendly names** like `soc` to raw register numbers

If no `register_map.yaml` exists, a default one will be created on first launch.

You can safely place your custom logic here to extend or override default behavior.

---

## 🧭 Shell Usage Tips

The shell is user-friendly and supports:

- **Tab completion** for commands and filenames
- **Arrow keys** (↑ and ↓) to navigate through previous commands
- **Inline help** using the `help` or `?` command

### Available Commands:

```
united-bms> help
```

| Command                              | Description                                      |
|--------------------------------------|--------------------------------------------------|
| `password`                           | Change debug user password                       |
| `config debug`                       | Start connection setup wizard                    |
| `config print`                       | List available custom override files             |
| `config edit <filename>`             | Edit an override file directly in the shell      |
| `read <slave> <block> <count>`       | Read registers from a BMS slave                  |
| `help` or `?`                        | Show command help                                |
| `exit`                               | Exit the shell                                   |

---

## 🔐 Change Debug User Password

To change the SSH password:

```bash
united-bms> password
```

You will be asked to enter and confirm the new password.

Internally it uses standard Linux password utilities inside the container.

---

## 📦 Home Assistant Add-on Integration

If you’re running outside the Supervisor (e.g., in Docker manually), make sure your container has access to:

```yaml
volumes:
  - /PATH/TO/ha/config:/config
  - /dev:/dev
```

Replace `/PATH/TO/ha/config` with the actual Home Assistant config path.

---

## 💬 Extending Support

To support new BMS protocols or register formats:

- Place your custom `.py` or `.yaml` logic into `/config/united_bms/`
- You can define your own register maps, protocol logic, or override behavior
- The framework will automatically use your customizations

---

## ✅ Summary

The United BMS Shell is a powerful and flexible interface for working directly with RS485-connected batteries in a Home Assistant environment. Whether you’re debugging, testing, or building custom support — the CLI makes it fast and safe.
