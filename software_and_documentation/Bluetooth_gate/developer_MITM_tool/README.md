# Ritar compatible batteries Bluetooth developer tool

Development board:
![ESP32-S3-DEV-KIT-N8R8](https://www.waveshare.com/wiki/ESP32-S3-DEV-KIT-N8R8)

## Description

Works as a long-range, wide-area repeater between native apps and the real master battery. 
It intercepts and logs packets between the battery and the app, outputting detailed logs 
to a web interface accessible via the device's IP address. 
Covers a long distance between the phone and the battery.

  
  ESP32 BLE MITM — logs -> WebSocket + SPIFFS (no reliance on Serial)
  - Peripheral (ESP emulates battery) <-> App
  - Central (ESP connects to real battery) <-> Battery
  - APP -> ESP writes are forwarded to battery (immediate if connected, otherwise queued)
  - Battery notifications are forwarded to APP
  - Logs: WebSocket (port 81) + SPIFFS (/ble_proxy_log.txt)
  - ArduinoOTA password: 1234

## Configuration

    // ---------- CONFIG ----------
    const char* WIFI_SSID = "Your_WiFi_SSID"; // Your WiFi AP SSID, for connect this device to your network
    const char* WIFI_PASS = "Your_Wifi_Pass"; // Your WiFi AP password, for connect this device
    const char* OTA_PASSWORD = "1234";

    const char* ADVERT_NAME = "RDAC_PROXY"; // this device name, what you will see in native BT App
    const char* TARGET_BATTERY_ADDR = "AC:23:3F:9E:E7:79"; // real battery MAC or "" to scan. Set master battery MAC (DIP swithes modbus ID 1)

    static BLEUUID SERVICE_UUID("0000fff0-0000-1000-8000-00805f9b34fb");
    static BLEUUID CHAR1_UUID ("0000fff1-0000-1000-8000-00805f9b34fb"); // notify/read
    static BLEUUID CHAR2_UUID ("0000fff2-0000-1000-8000-00805f9b34fb"); // write

    const char* LOG_FILE_PATH = "/ble_proxy_log.txt";

    // Time / NTP
    bool g_timeSynced = false;          // becomes true after successful NTP
    const char* NTP_POOL1 = "pool.ntp.org";
    const char* NTP_POOL2 = "time.google.com";
    // POSIX TZ string for Kyiv (handles DST). If issues, you can use simpler "Europe/Kyiv".
    const char* TZ_STRING = "EET-2EEST,M3.5.0/3,M10.5.0/4";

## Usage

    Prepare source variables for your local equipment

    Upload source to board via Arduino IDE. OTA updates are available using OTA_PASSWORD (default "1234")

    Connect to the RDAC_Proxy battery by native Bluetooth App from store :

![Bluetooth Li](https://play.google.com/store/apps/details?id=com.canrs.bluetooth.li&hl=ru) </br>
![Neuton Power](https://play.google.com/store/apps/details?id=com.powy.hier)

    Open the web interface at http://<ESP_IP>/ to monitor logs.

    All packets are intercepted and relayed between the app and battery.

Example logs:

![screenshot](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/developer_MITM_tool/mitm_1.jpg)
![screenshot](https://github.com/mamontuka/ritar-bms-ha/blob/main/software_and_documentation/Bluetooth_gate/developer_MITM_tool/mitm_2.jpg)


