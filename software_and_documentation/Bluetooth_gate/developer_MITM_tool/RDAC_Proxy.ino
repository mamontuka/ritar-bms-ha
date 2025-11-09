/*
 * Copyright (c) 2025, Oleh Mamont
 * This file is part of the Ritar BMS / United BMS project.
 *
 * Uses NimBLE library version 1.4.3
 *
 * Licensed under the GNU General Public License v3.0 (GPLv3)
 */

/*
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
*/

#include <NimBLEDevice.h>
#include <SPIFFS.h>
#include <WebServer.h>
#include <WebSocketsServer.h>
#include <WiFi.h>
#include <ArduinoOTA.h>
#include <deque>
#include <vector>
#include <ctime>
#include <time.h>
#include <sys/time.h>
#include <stdarg.h>

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

// ---------- GLOBALS ----------
WebServer httpServer(80);
WebSocketsServer webSocket(81); // websocket server on port 81

// Peripheral (ESP emulates battery)
NimBLEServer* pServer = nullptr;
NimBLECharacteristic* pPeripheralChar1 = nullptr; // fff1: notify/read
NimBLECharacteristic* pPeripheralChar2 = nullptr; // fff2: write
bool appConnected = false;

// Central (ESP -> real battery)
NimBLEClient* pClient = nullptr;
NimBLERemoteCharacteristic* pRemoteChar1 = nullptr;
NimBLERemoteCharacteristic* pRemoteChar2 = nullptr;
bool batteryConnected = false;

struct QueuedWrite { std::vector<uint8_t> data; };
std::deque<QueuedWrite> writeQueue;
const size_t MAX_QUEUE = 256;
const int WRITE_RETRY_COUNT = 3;
const int WRITE_RETRY_DELAY_MS = 80;

// ---------- TIME helpers ----------
String getTimeStamp() {
  if (!g_timeSynced) return String("");

  time_t now = time(nullptr);
  if (now <= (time_t)100000) return String(""); // clearly invalid time

  struct tm tm;
  localtime_r(&now, &tm);
  char buf[64];
  strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &tm);
  return String(buf);
}

void syncTimeWithNTP() {
  // Set TZ
  setenv("TZ", TZ_STRING, 1);
  tzset();

  // Configure NTP servers; note: 0,0 means use TZ for local time
  configTime(0, 0, NTP_POOL1, NTP_POOL2);

  // Wait for NTP sync — timeout ~12s
  const int maxTrials = 24; // 24 * 500ms = 12s
  int tries = 0;
  while (tries++ < maxTrials) {
    time_t now = time(nullptr);
    struct tm tm;
    if (now > 1600000000 && localtime_r(&now, &tm) && (tm.tm_year + 1900) > 2020) {
      g_timeSynced = true;
      // log the success
      // Use logToWebAndFile via slogf (logToWebAndFile will add timestamp now)
      // But ensure g_timeSynced is set before calling slogf so timestamp is produced.
      slogf("[TIME] NTP sync OK: %s");
      return;
    }
    delay(500);
  }
  g_timeSynced = false;
  // If failed, write a message without timestamp
  // We call logToWebAndFile directly with plain string (it will not add timestamp because g_timeSynced==false)
  File f = SPIFFS.open(LOG_FILE_PATH, FILE_APPEND);
  if (f) { f.println(String("[TIME] NTP sync FAILED (timeout)")); f.close(); }
}

// ---------- LOG HELPERS (Web + SPIFFS) ----------
// Modified so that when g_timeSynced==true logs are prefixed with timestamp
// alreadyHasTS: If true, the string already contains a timestamp, no need to add it
const size_t MAX_LOG_SIZE = 64 * 1024; // 64 KB max log file

// Forward declaration
void logToWebAndFile(const String &s, bool alreadyHasTS = false);

// Simple string log
void slog(const char* s) { 
    logToWebAndFile(String(s)); 
}

// Formatted log (like printf)
void slogf(const char* fmt, ...) {
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    logToWebAndFile(String(buf));
}

// Hex dump with tag
void slogHexTag(const char* tag, const uint8_t* data, size_t len) {
    char buf[1024];
    int p = snprintf(buf, sizeof(buf), "[%s] ", tag);
    for (size_t i = 0; i < len && p < (int)sizeof(buf)-4; ++i) {
        p += snprintf(buf + p, sizeof(buf) - p, "%02X ", data[i]);
    }
    buf[sizeof(buf)-1] = 0;
    logToWebAndFile(String(buf), false);
}

// Main logging function with timestamp and file size limit
void logToWebAndFile(const String &s, bool alreadyHasTS) {
    String tmp;

    // --- Add timestamp ---
    if (!alreadyHasTS) {
        String ts = getTimeStamp();
        if (ts.length() > 0) tmp = String("[") + ts + "] " + s;
        else tmp = s; // time not yet synced
    } else {
        tmp = s;
    }

    // --- Broadcast to WebSocket if clients connected ---
    if (webSocket.connectedClients() > 0) {
        webSocket.broadcastTXT(tmp);
    }

    // --- Write to SPIFFS with size check ---
    if (!SPIFFS.exists(LOG_FILE_PATH)) {
        // File does not exist yet, just create and append
        File f = SPIFFS.open(LOG_FILE_PATH, FILE_APPEND);
        if (f) { f.println(tmp); f.close(); }
        return;
    }

    File f = SPIFFS.open(LOG_FILE_PATH, FILE_APPEND);
    if (!f) return;

    if (f.size() > MAX_LOG_SIZE) {
        f.close();

        // Read last MAX_LOG_SIZE/2 bytes
        File fRead = SPIFFS.open(LOG_FILE_PATH, FILE_READ);
        if (!fRead) return;

        size_t startPos = fRead.size() > MAX_LOG_SIZE/2 ? fRead.size() - MAX_LOG_SIZE/2 : 0;
        fRead.seek(startPos);
        String newContent = fRead.readString();
        fRead.close();

        // Overwrite file with trimmed content
        SPIFFS.remove(LOG_FILE_PATH);
        File fWrite = SPIFFS.open(LOG_FILE_PATH, FILE_WRITE);
        if (fWrite) {
            fWrite.print(newContent);
            fWrite.println(tmp); // append new line
            fWrite.close();
        }
    } else {
        f.println(tmp);
        f.close();
    }
}

// ---------- UTIL ----------
std::vector<uint8_t> hexToBytes(const String &hex) {
  std::vector<uint8_t> out;
  String s = hex; s.replace(" ", ""); s.toUpperCase();
  for (int i=0;i+1<(int)s.length(); i+=2) {
    char a = s[i], b = s[i+1];
    uint8_t hi = (a>='0'&&a<='9')?a-'0':a-'A'+10;
    uint8_t lo = (b>='0'&&b<='9')?b-'0':b-'A'+10;
    out.push_back((hi<<4)|lo);
  }
  return out;
}

// ---------- BLE: Peripheral callbacks ----------
class PeripheralCallbacks : public NimBLECharacteristicCallbacks {
  void onRead(NimBLECharacteristic* pChar) override {
    logToWebAndFile(String("[APP read] fff1 requested"));
    if (batteryConnected && pRemoteChar1 && pRemoteChar1->canRead()) {
      try {
        std::string rv = pRemoteChar1->readValue();
        if (!rv.empty()) {
          pPeripheralChar1->setValue((const uint8_t*)rv.data(), rv.size());
          slogHexTag("Reply->APP (fff1)", (const uint8_t*)rv.data(), rv.size());
        } else {
          logToWebAndFile(String("[APP read] remote read empty"));
        }
      } catch(...) { logToWebAndFile(String("[APP read] exception during remote read")); }
    } else {
      logToWebAndFile(String("[APP read] battery not connected or remote fff1 not readable"));
    }
  }

  void onWrite(NimBLECharacteristic* pChar) override {
    std::string val = pChar->getValue();
    if (val.size() == 0) return;
    const uint8_t* data = (const uint8_t*)val.data();
    size_t len = val.size();

    if (pChar == pPeripheralChar2) {
      slogHexTag("APP->ESP fff2", data, len);
      if (batteryConnected && pRemoteChar2) {
        bool ok = false;
        for (int r=0;r<WRITE_RETRY_COUNT;++r) {
          ok = pRemoteChar2->writeValue(data, len, false);
          if (ok) break;
          delay(WRITE_RETRY_DELAY_MS);
        }
        if (ok) slogHexTag("ESP->BATTERY fff2", data, len);
        else {
          if (writeQueue.size() < MAX_QUEUE) writeQueue.push_back({std::vector<uint8_t>(data,data+len)});
          logToWebAndFile(String("[APP->ESP] fff2 forward failed -> queued"));
        }
      } else {
        if (writeQueue.size() < MAX_QUEUE) writeQueue.push_back({std::vector<uint8_t>(data,data+len)});
        logToWebAndFile(String("[APP->ESP] fff2 queued (battery not connected)"));
      }
    } else if (pChar == pPeripheralChar1) {
      slogHexTag("APP->ESP fff1 (write)", data, len);
      // forward similarly to fff1 on remote if exists, else queue
      if (batteryConnected && pRemoteChar1) {
        bool ok = false;
        for (int r=0;r<WRITE_RETRY_COUNT;++r) {
          ok = pRemoteChar1->writeValue(data, len, false);
          if (ok) break;
          delay(WRITE_RETRY_DELAY_MS);
        }
        if (ok) slogHexTag("ESP->BATTERY fff1", data, len);
        else {
          if (writeQueue.size() < MAX_QUEUE) writeQueue.push_back({std::vector<uint8_t>(data,data+len)});
          logToWebAndFile(String("[APP->ESP] fff1 forward failed -> queued"));
        }
      } else {
        if (writeQueue.size() < MAX_QUEUE) writeQueue.push_back({std::vector<uint8_t>(data,data+len)});
        logToWebAndFile(String("[APP->ESP] fff1 queued (battery not connected)"));
      }
    } else {
      logToWebAndFile(String("[APP->ESP] write to unknown peripheral char"));
    }
  }
};

class ServerCbs : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer* srv) override {
    appConnected = true;
    logToWebAndFile(String("[APP] connected to ESP peripheral"));
    // attempt to connect to battery as soon as app connects
    // (non-blocking: main loop will try)
  }
  void onDisconnect(NimBLEServer* srv) override {
    appConnected = false;
    logToWebAndFile(String("[APP] disconnected from ESP peripheral"));
  }
};

// ---------- BLE: Central callbacks ----------
class ClientCbs : public NimBLEClientCallbacks {
  void onConnect(NimBLEClient* cli) override {
    batteryConnected = true;
    logToWebAndFile(String("[ESP] connected to real battery"));
    // find service/chars performed in connectToBatteryByAddr
  }
  void onDisconnect(NimBLEClient* cli) override {
    batteryConnected = false;
    logToWebAndFile(String("[ESP] disconnected from real battery"));
    pRemoteChar1 = nullptr;
    pRemoteChar2 = nullptr;
    // cleanup client object
    if (pClient) { NimBLEDevice::deleteClient(pClient); pClient = nullptr; }
  }
};

// battery notify callback
static void batteryNotifyCB(NimBLERemoteCharacteristic* rc, uint8_t* data, size_t len, bool isNotify) {
  slogHexTag("BATTERY->ESP (notify)", data, len);
  if (appConnected && pPeripheralChar1) {
    pPeripheralChar1->setValue(data, len);
    pPeripheralChar1->notify(true);
    slogHexTag("ESP->APP (notify)", data, len);
  } else {
    logToWebAndFile(String("[BATTERY notify] no APP connected - dropped"));
  }
}

// ---------- Scan callbacks ----------
class ScanCbs : public NimBLEAdvertisedDeviceCallbacks {
  void onResult(NimBLEAdvertisedDevice* adv) override {
    std::string sd = adv->getServiceData();
    if (sd.size() > 0) {
      String hex="";
      for (size_t i=0;i<sd.size();++i){ char b[4]; sprintf(b,"%02X",(uint8_t)sd[i]); hex += String(b); }
      slogf("Scan found %s svcdata=%s", adv->getAddress().toString().c_str(), hex.c_str());
    } else {
      slogf("Scan found %s (no svcdata)", adv->getAddress().toString().c_str());
    }
  }
};

// ---------- Connect helper ----------
bool connectToBatteryByAddr(const std::string &addrStr) {
  if (pClient && pClient->isConnected()) return true;
  slogf("Connecting to battery %s ...", addrStr.c_str());

  pClient = NimBLEDevice::createClient();
  pClient->setClientCallbacks(new ClientCbs(), false);

  NimBLEAddress addr(addrStr);
  bool ok = pClient->connect(addr);
  if (!ok) {
    logToWebAndFile(String("[ESP connect] connect() returned false"));
    NimBLEDevice::deleteClient(pClient);
    pClient = nullptr;
    return false;
  }

  // service + characteristics discovery
  NimBLERemoteService* rs = pClient->getService(SERVICE_UUID);
  if (!rs) {
    logToWebAndFile(String("[ESP connect] service fff0 not found"));
    return false;
  }

  pRemoteChar1 = rs->getCharacteristic(CHAR1_UUID);
  pRemoteChar2 = rs->getCharacteristic(CHAR2_UUID);

  if (pRemoteChar1) {
    logToWebAndFile(String("[ESP connect] remote fff1 found"));
    if (pRemoteChar1->canNotify()) {
      pRemoteChar1->subscribe(true, batteryNotifyCB);
      logToWebAndFile(String("[ESP connect] subscribed to remote fff1 notifications"));
    } else logToWebAndFile(String("[ESP connect] remote fff1 cannot notify"));
  } else logToWebAndFile(String("[ESP connect] remote fff1 NOT found"));

  if (pRemoteChar2) logToWebAndFile(String("[ESP connect] remote fff2 found"));
  else logToWebAndFile(String("[ESP connect] remote fff2 NOT found"));

  batteryConnected = true;

  // initial read from remote fff1 if readable
  if (pRemoteChar1 && pRemoteChar1->canRead()) {
    try {
      std::string rv = pRemoteChar1->readValue();
      if (!rv.empty()) {
        slogHexTag("Initial read fff1", (const uint8_t*)rv.data(), rv.size());
        if (appConnected && pPeripheralChar1) {
          pPeripheralChar1->setValue((const uint8_t*)rv.data(), rv.size());
          pPeripheralChar1->notify(true);
          logToWebAndFile(String("[ESP] initial battery value pushed to APP"));
        }
      }
    } catch(...) {
      logToWebAndFile(String("[ESP] exception during initial read"));
    }
  }

  return true;
}

// ---------- process queued writes ----------
void processWriteQueueOnce() {
  if (!batteryConnected || !pRemoteChar2) return;
  if (writeQueue.empty()) return;

  auto &qw = writeQueue.front();
  bool ok = false;
  for (int r=0;r<WRITE_RETRY_COUNT;++r) {
    ok = pRemoteChar2->writeValue(qw.data.data(), qw.data.size(), false);
    if (ok) break;
    delay(WRITE_RETRY_DELAY_MS);
  }
  if (ok) {
    slogHexTag("QUEUED->BATTERY forwarded", qw.data.data(), qw.data.size());
    writeQueue.pop_front();
  } else {
    logToWebAndFile(String("[QUEUE] forward failed this round (will retry)"));
  }
}

// ---------- Peripheral setup ----------
void setupPeripheral() {
  logToWebAndFile(String("[SETUP] peripheral start"));
  NimBLEDevice::setPower(ESP_PWR_LVL_P9);
  pServer = NimBLEDevice::createServer();
  pServer->setCallbacks(new ServerCbs());

  NimBLEService* svc = pServer->createService(SERVICE_UUID);

  pPeripheralChar1 = svc->createCharacteristic(
    CHAR1_UUID,
    NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::NOTIFY
  );

  pPeripheralChar2 = svc->createCharacteristic(
    CHAR2_UUID,
    NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR
  );

  static PeripheralCallbacks perCb; // keep alive
  pPeripheralChar1->setCallbacks(&perCb);
  pPeripheralChar2->setCallbacks(&perCb);

  svc->start();

  NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->addServiceUUID(SERVICE_UUID);
  adv->setName(ADVERT_NAME);

  NimBLEDevice::startAdvertising();
  logToWebAndFile(String("[SETUP] peripheral advertising started"));
}

// ---------- Web UI ----------
const char MAIN_page[] PROGMEM = R"rawliteral(
<!doctype html><html><head><meta charset="utf-8"><title>Mamontuka's BLE MITM Tool</title></head>
<body><h3>Ritar compatible BLE battery MITM — Live Logs</h3><pre id="log">Connecting...</pre>
<script>
let ws = new WebSocket('ws://' + location.hostname + ':81/');
ws.onopen = ()=>{ document.getElementById('log').textContent='[ws] connected\n'; };
ws.onmessage = (evt)=>{ let l=document.getElementById('log'); l.textContent += evt.data + '\n'; l.scrollTop = l.scrollHeight; };
</script></body></html>
)rawliteral";
void handleRoot() { httpServer.send(200, "text/html", MAIN_page); }

// ---------- WebSocket event ----------
void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  if (type == WStype_TEXT) {
    String cmd = String((char*)payload);
    slogf("WS cmd: %s", cmd.c_str());
    if (cmd == "scan") {
      NimBLEScan* pScan = NimBLEDevice::getScan();
      pScan->setAdvertisedDeviceCallbacks(new ScanCbs());
      pScan->setActiveScan(true);
      pScan->start(6, false);
    } else if (cmd.startsWith("connect ")) {
      String addr = cmd.substring(8);
      slogf("WS requested connect to %s", addr.c_str());
      connectToBatteryByAddr(std::string(addr.c_str()));
    }
  }
}

// ---------- SETUP / LOOP ----------
unsigned long lastQueueMillis = 0;
unsigned long lastConnectMillis = 0;

void setup() {
  // no reliance on Serial for user environment; logs go to websocket & file
  Serial.begin(115200);
  delay(10);

  if (!SPIFFS.begin(true)) {
    // if SPIFFS fails, still continue - but can't save logs
  }

  logToWebAndFile(String("[BOOT] starting ESP32 BLE MITM (OTA pwd 1234)"));

  // NimBLE peripheral first
  NimBLEDevice::init(ADVERT_NAME);
  NimBLEDevice::setSecurityAuth(false, false, false);
  setupPeripheral();

  // WiFi
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  logToWebAndFile(String("[WIFI] connecting..."));
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries++ < 40) { delay(250); }
  if (WiFi.status() == WL_CONNECTED) {
    slogf("WIFI: %s", WiFi.localIP().toString().c_str());
    // Time synchronization via NTP (blocking, short timeout)
    syncTimeWithNTP();
  } else {
    logToWebAndFile(String("[WIFI] not connected"));
  }

  // OTA
  ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.begin();
  logToWebAndFile(String("[OTA] ready"));

  // HTTP + WS
  httpServer.on("/", handleRoot);
  httpServer.begin();
  webSocket.begin();
  webSocket.onEvent(webSocketEvent);
  logToWebAndFile(String("[WEB] HTTP + WebSocket started"));

  lastConnectMillis = millis();
  // try initial connect if configured
  if (String(TARGET_BATTERY_ADDR).length() > 0) {
    connectToBatteryByAddr(std::string(TARGET_BATTERY_ADDR));
  }
}

void loop() {
  ArduinoOTA.handle();
  webSocket.loop();
  httpServer.handleClient();

  // reconnect attempts every 4s if disconnected
  if (!batteryConnected && millis() - lastConnectMillis > 4000) {
    lastConnectMillis = millis();
    if (String(TARGET_BATTERY_ADDR).length() > 0) {
      connectToBatteryByAddr(std::string(TARGET_BATTERY_ADDR));
    } else {
      NimBLEScan* pScan = NimBLEDevice::getScan();
      pScan->setAdvertisedDeviceCallbacks(new ScanCbs());
      pScan->setActiveScan(true);
      pScan->start(6, false);
    }
  }

  // process queued write (throttled)
  if (millis() - lastQueueMillis > 80) {
    lastQueueMillis = millis();
    processWriteQueueOnce();
  }

  delay(5);
}
