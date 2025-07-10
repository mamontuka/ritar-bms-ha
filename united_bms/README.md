# United BMS Feature for Ritar BMS Addon

## This feature allows you to extend and customize your Ritar BMS Home Assistant addon by loading override Python modules from a fixed folder in your Home Assistant config directory.
### What is United BMS Feature?

The United BMS feature provides a custom modules directory (/config/united_bms) where you can place your own versions of key Python modules that the addon loads dynamically at runtime. 

This lets you **create by self, BMS addon for batteries manufactured by other vendors !** and:

    Customize battery parsing logic
    Override Modbus register definitions
    Adjust temperature parsing or any other core logic without rebuilding the addon
    Test new features or bug fixes easily by editing Python files directly in your Home Assistant config

**How it Works**

At startup, the addon tries to load modules in this order:
    From the fixed override path /config/united_bms (e.g. /config/united_bms/modbus_registers.py)
    If not found, fallback to the internal default module bundled in the addon

This means if you provide a custom modbus_registers.py in /config/united_bms/, your version will be used instead of the built-in one.

Getting Started
Prerequisites

    You already have the Ritar BMS addon installed in Home Assistant
    You have access to your Home Assistant configuration directory (usually /config)

**Step 1: Create the override directory**

Using your favorite file editor or Samba share, create the directory:

/config/united_bms

**Step 2: Place your custom Python files**

Copy or create any of the following files you want to override inside /config/united_bms:

    modbus_registers.py
    parser_battery.py
    parser_temperature.py
    main_settings.py
    modbus_inverter.py
    modbus_eeprom.py
    modbus_battery.py

**You do not need to override all files — only the ones you want to customize.**

**Step 3: Restart the addon**

After placing your override files, restart the Ritar BMS addon. You should see logs indicating that your override modules were loaded from /config/united_bms.

**Step 4: Verify**

Check the addon logs for messages like:

    [INFO] Loaded override modbus_registers.py from /config/united_bms/modbus_registers.py

If you do, your overrides are active.
Notes

    The directory /config/united_bms is fixed in the addon and cannot be changed via configuration options.
    The addon falls back to internal modules if no override file is found.
    Changes to override files require an addon restart to take effect.
    Make sure your custom Python files are syntactically correct to avoid import errors.

Troubleshooting

    If overrides are not loaded, verify your files are correctly placed in /config/united_bms inside the Home Assistant container.
    Use docker exec or the Home Assistant terminal addon to inspect files inside the container.
    Check file permissions to ensure the addon can read the override files.

Example Docker Volume Mapping

If you are running the addon via Docker Compose manually, mount your override directory like this:

    volumes:
      - ./config.yaml:/workdir/config.yaml
      - ./united_bms:/config/united_bms
      - /dev:/dev

