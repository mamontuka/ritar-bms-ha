/*
 * Copyright (c) 2025, Oleh Mamont
 * This file is part of the Ritar BMS / United BMS project.
 *
 * Uses NimBLE library version 1.4.3
 *
 * Licensed under the GNU General Public License v3.0 (GPLv3)
 */

/*
In proxy mode works as a long-range, wide-area repeater between native apps and the real master battery. 
It intercepts and logs packets between the battery and the app, outputting detailed logs 
to a web interface accessible via the device's IP address. 
Covers a long distance between the phone and the battery.
In python-driven mode works as connector betwen Homeassistant Ritar-BMS Addon and master battery.

  
  ESP32 BLE MITM — proxy + python-driven
  - Peripheral (ESP emulates battery) <-> App
  - Central (ESP connects to real battery) <-> Battery
  - Modes:
      * proxy: APP <-> ESP <-> Battery (real proxy)
      * python-driven: Python script <-> ESP <-> Battery (APP ignored)
  - Logs: WebSocket / API (default port 50501) (RAM only) + SPIFFS for mode/target
  - Mode persisted in /mode.cfg, target MAC persisted in /target.cfg
  - Arduino IDE OTA password: 1234
  - Arduino IDE OTA TURNED OFF in production version (in setup / loop section) ! 
  - Enable Arduino IDE OTA only for development purposes !
*/

#include <NimBLEDevice.h>
#include <SPIFFS.h>
#include "esp_partition.h"
#include "esp_ota_ops.h"
#include <WebServer.h>
#include <WebSocketsServer.h>
#include <WiFi.h>
#include <Preferences.h>
#include <DNSServer.h>
#include <ArduinoOTA.h>
#include <Update.h>
#include <deque>
#include <vector>
#include <time.h>
#include <ctime>
#include <cstdarg>


#define FIRMWARE_VERSION "1.1"


// ------------------------- CONFIG ---------------------------
Preferences pref;
String wifi_ssid;
String wifi_pass;
bool hasWiFiConfig = false;

bool useStaticIP = false;
String ip_addr, netmask, gateway;

const String DEFAULT_ADMIN = "1234";
String admin_pass = DEFAULT_ADMIN;
bool loggedIn = false;

const char* OTA_PASSWORD = "1234";

const char* ADVERT_NAME = "RDAC_PROXY";
String TARGET_BATTERY_ADDR = "AC:23:3F:9E:E7:79";  // default target, can be changed via UI

static BLEUUID SERVICE_UUID("0000fff0-0000-1000-8000-00805f9b34fb");
static BLEUUID CHAR1_UUID("0000fff1-0000-1000-8000-00805f9b34fb");  // notify/read (from battery -> app)
static BLEUUID CHAR2_UUID("0000fff2-0000-1000-8000-00805f9b34fb");  // write (from app -> battery)

const char* MODE_FILE = "/mode.cfg";
const char* TARGET_FILE = "/target.cfg";

// wifi background scan
struct WiFiNetwork {
  String ssid;
  int32_t rssi;
  bool secure;
};

#define MAX_WIFI_NETWORKS 30
WiFiNetwork scannedNetworks[MAX_WIFI_NETWORKS];
int scannedCount = 0;

unsigned long lastScanTime = 0;
const unsigned long scanInterval = 60000; // 60 sec


// NTP
const char* NTP_SERVERS[] = { "pool.ntp.org", "time.google.com" };
const int NTP_SERVER_COUNT = 2;
long GMT_OFFSET_SEC = 2 * 3600;  // Europe/Kyiv (UTC+2) — adjust if DST needed
int DAYLIGHT_OFFSET_SEC = 1;     // change if you DONT want automatic DST offset


// ------------------------- GLOBALS --------------------------
WebServer httpServer(80);


WebSocketsServer* webSocket = nullptr;
uint16_t websocket_port = 50501; // default port


DNSServer dnsServer;
const byte DNS_PORT = 53;


NimBLEServer* pServer = nullptr;
NimBLECharacteristic* pPeripheralChar1 = nullptr;  // fff1: notify/read (app sees this)
NimBLECharacteristic* pPeripheralChar2 = nullptr;  // fff2: write (app writes here)
bool appConnected = false;

NimBLEClient* pClient = nullptr;
NimBLERemoteCharacteristic* pRemoteChar1 = nullptr;  // remote battery fff1
NimBLERemoteCharacteristic* pRemoteChar2 = nullptr;  // remote battery fff2
bool batteryConnected = false;

struct QueuedWrite {
  std::vector<uint8_t> data;
};
std::deque<QueuedWrite> writeQueue;
const size_t MAX_QUEUE = 256;
const int WRITE_RETRY_COUNT = 3;
const int WRITE_RETRY_DELAY_MS = 80;

// Mode: false = proxy, true = python-driven
bool pythonDriven = false;

// advertising serviceData copy (if discovered)
std::string cachedSvcData = "";

// keep track whether SPIFFS successfully mounted
bool spiffsMounted = false;


// partitions
void printPartitions() {
  Serial.println("=== Partition list ===");
  esp_partition_iterator_t it = esp_partition_find(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_ANY, NULL);
  while (it) {
    const esp_partition_t *p = esp_partition_get(it);
    Serial.printf("APP: label=%s, addr=0x%06x, size=0x%06x, subtype=%d\n", p->label, p->address, p->size, p->subtype);
    it = esp_partition_next(it);
  }
  it = esp_partition_find(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_ANY, NULL);
  while (it) {
    const esp_partition_t *p = esp_partition_get(it);
    Serial.printf("DATA: label=%s, addr=0x%06x, size=0x%06x, subtype=%d\n", p->label, p->address, p->size, p->subtype);
    it = esp_partition_next(it);
  }

  const esp_partition_t *ota = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_OTA, "otadata");
  if (ota) Serial.printf("otadata: label=%s, addr=0x%06x, size=0x%06x\n", ota->label, ota->address, ota->size);
  else Serial.println("otadata: NOT FOUND");
  Serial.println("======================");
}


// -------------------- MODE persistence ----------------------
// forward declaration
void applyMode();

bool writeFileWithRetry(const char* path, const String& content, int retries = 3, int delayMs = 200) {
  if (!spiffsMounted) return false;
  for (int i = 0; i < retries; ++i) {
    File f = SPIFFS.open(path, FILE_WRITE);
    if (f) {
      f.print(content);
      f.close();
      return true;
    }
    delay(delayMs);
  }
  return false;
}

void saveModeToSPIFFS() {
  // Try to write to SPIFFS; if it fails, still keep mode in RAM and log.
  if (!spiffsMounted) {
    String msg = String("[MODE] SPIFFS not mounted, persisting in RAM only. Mode: ") + (pythonDriven ? "python-driven" : "proxy");
    webBroadcastSafe(msg);
    logToWebAndFile(msg);
    return;
  }

  String payload = pythonDriven ? "1" : "0";
  bool ok = writeFileWithRetry(MODE_FILE, payload, 3, 150);
  if (!ok) {
    slog("[MODE] Failed to open mode file for write (will persist in RAM only)");
    String msg = String("[MODE] Persist failed - mode in RAM: ") + (pythonDriven ? "python-driven" : "proxy");
    webBroadcastSafe(msg);
    logToWebAndFile(msg);
    return;
  }
  String msg = String("[MODE] Saved mode: ") + (pythonDriven ? "python-driven" : "proxy");
  webBroadcastSafe(msg);
  logToWebAndFile(msg);
}

void loadModeFromSPIFFS() {
  if (!spiffsMounted) {
    pythonDriven = false;  // default if no FS
    String msg = String("[MODE] SPIFFS not mounted - using default mode: proxy");
    webBroadcastSafe(msg);
    logToWebAndFile(msg);
    return;
  }

  if (!SPIFFS.exists(MODE_FILE)) {
    pythonDriven = false;
    saveModeToSPIFFS();
    return;
  }
  File f = SPIFFS.open(MODE_FILE, FILE_READ);
  if (!f) {
    slog("[MODE] Failed to open mode file for read - using default proxy");
    pythonDriven = false;
    return;
  }
  String s = f.readStringUntil('\n');
  f.close();
  s.trim();
  pythonDriven = (s.length() > 0 && s[0] == '1');
  String msg = String("[MODE] Loaded mode: ") + (pythonDriven ? "python-driven" : "proxy");
  webBroadcastSafe(msg);
  logToWebAndFile(msg);
}


// --------------------- TARGET persistence -------------------
void saveTargetToSPIFFS() {
  if (!spiffsMounted) {
    slog("[TARGET] SPIFFS not mounted - target persisted in RAM only");
    slogf("[TARGET] RAM target: %s", TARGET_BATTERY_ADDR.c_str());
    return;
  }
  bool ok = writeFileWithRetry(TARGET_FILE, TARGET_BATTERY_ADDR, 3, 150);
  if (!ok) {
    slog("[TARGET] Failed to open target file for write");
    slogf("[TARGET] RAM target: %s", TARGET_BATTERY_ADDR.c_str());
    return;
  }
  slogf("[TARGET] Saved target: %s", TARGET_BATTERY_ADDR.c_str());
}

void loadTargetFromSPIFFS() {
  if (!spiffsMounted) {
    TARGET_BATTERY_ADDR = "";  // default
    slog("[TARGET] SPIFFS not mounted - no persisted target");
    return;
  }
  if (!SPIFFS.exists(TARGET_FILE)) {
    TARGET_BATTERY_ADDR = "";
    saveTargetToSPIFFS();
    return;
  }
  File f = SPIFFS.open(TARGET_FILE, FILE_READ);
  if (!f) {
    slog("[TARGET] Failed to open target file for read");
    return;
  }
  String s = f.readStringUntil('\n');
  f.close();
  s.trim();
  TARGET_BATTERY_ADDR = s;
  slogf("[TARGET] Loaded target: %s", TARGET_BATTERY_ADDR.c_str());
}


// ----------------------- WiFi -------------------------------
bool loadWiFi() {
  pref.begin("wifi", true);
  wifi_ssid = pref.getString("ssid", "");
  wifi_pass = pref.getString("pass", "");
  useStaticIP = pref.getBool("useStatic", false);
  ip_addr = pref.getString("ip", "");
  netmask = pref.getString("mask", "");
  gateway = pref.getString("gw", "");
  admin_pass = pref.getString("admin", DEFAULT_ADMIN);
  pref.end();
  return (wifi_ssid.length() > 0);
}

void saveWiFi(const String &s, const String &p) {
  pref.begin("wifi", false);
  pref.putString("ssid", s);
  pref.putString("pass", p);
  pref.end();
}

void saveIPSettings() {
  pref.begin("wifi", false);
  pref.putBool("useStatic", useStaticIP);
  pref.putString("ip", ip_addr);
  pref.putString("mask", netmask);
  pref.putString("gw", gateway);
  pref.end();
}

// wifi scan at device startup
void wifiScanFirstTime() {
  int n = WiFi.scanNetworks();
  scannedCount = n > MAX_WIFI_NETWORKS ? MAX_WIFI_NETWORKS : n;
  for (int i = 0; i < scannedCount; ++i) {
    scannedNetworks[i].ssid = WiFi.SSID(i);
    scannedNetworks[i].rssi = WiFi.RSSI(i);
    scannedNetworks[i].secure = WiFi.encryptionType(i) != WIFI_AUTH_OPEN;
  }
  WiFi.scanDelete();
  lastScanTime = millis();
}

// wifi background scan
void wifiScanLoop() {
  if (millis() - lastScanTime < scanInterval) return;
  lastScanTime = millis();

  int n = WiFi.scanNetworks();
  scannedCount = n > MAX_WIFI_NETWORKS ? MAX_WIFI_NETWORKS : n;
  for (int i = 0; i < scannedCount; ++i) {
    scannedNetworks[i].ssid = WiFi.SSID(i);
    scannedNetworks[i].rssi = WiFi.RSSI(i);
    scannedNetworks[i].secure = WiFi.encryptionType(i) != WIFI_AUTH_OPEN;
  }
  WiFi.scanDelete(); // clean memory
}


// ----------------------- AP + Captive Portal ----------------
void startAP() {
  Serial.println("Starting AP mode...");
  WiFi.mode(WIFI_AP);
  WiFi.softAP("Ritar BT Gate", "");
  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP());
  dnsServer.start(DNS_PORT, "*", WiFi.softAPIP());
}

bool tryWiFi() {
  Serial.printf("Connecting to SSID='%s'\n", wifi_ssid.c_str());
  WiFi.mode(WIFI_STA);
  if (useStaticIP && ip_addr.length() > 0) {
    IPAddress ip, nm, gw;
    ip.fromString(ip_addr);
    nm.fromString(netmask);
    gw.fromString(gateway);
    WiFi.config(ip, nm, gw);
  }
  WiFi.begin(wifi_ssid.c_str(), wifi_pass.c_str());
  unsigned long start = millis();
  while (millis() - start < 15000) {
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("Connected, IP=" + WiFi.localIP().toString());
      return true;
    }
    delay(250);
  }
  Serial.println("\nWiFi failed");
  return false;
}


// ---------------------- websocket / api port ----------------
void loadWebsocketSettings() {
  pref.begin("wifi", true);
  websocket_port = pref.getUShort("ws_port", 50501);
  pref.end();
}

void saveWebsocketPort(uint16_t p) {
  pref.begin("wifi", false);
  pref.putUShort("ws_port", p);
  pref.end();
  websocket_port = p;
}

void startWebSocket(uint16_t port) {
    if (webSocket) {
        delete webSocket;
        webSocket = nullptr;
    }

    websocket_port = port;
    webSocket = new WebSocketsServer(websocket_port);
    webSocket->onEvent(webSocketEvent);
    webSocket->begin();

    slog( (String("[WEB] WebSocket started on port ") + websocket_port).c_str() );
}


// --------------------- NTP / time sync ----------------------

// load/save time settings
void loadTimeSettings() {
  pref.begin("time", true);
  GMT_OFFSET_SEC = pref.getLong("gmt_offset", 2 * 3600);
  DAYLIGHT_OFFSET_SEC = pref.getInt("dst_offset", 0);
  pref.end();
  slogf("[TIME] loaded GMT_OFFSET=%ld DST=%d", GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC);
}

void saveTimeSettings() {
  pref.begin("time", false);
  pref.putLong("gmt_offset", GMT_OFFSET_SEC);
  pref.putInt("dst_offset", DAYLIGHT_OFFSET_SEC);
  pref.end();
  slogf("[TIME] saved GMT_OFFSET=%ld DST=%d", GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC);
}

// time sync
void startNtpAndSync() {
  // configure NTP servers, try to sync time
  for (int i = 0; i < NTP_SERVER_COUNT; ++i) {
    // prefer to give a list to configTime; call once is sufficient
  }
  configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVERS[0], NTP_SERVERS[1]);
  slog("[NTP] configured NTP servers");

  // wait for time to be set (with timeout)
  const int maxWaitMs = 8000;
  int waited = 0;
  struct tm timeinfo;
  while (waited < maxWaitMs) {
    if (getLocalTime(&timeinfo, 2000)) {
      char buf[64];
      strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &timeinfo);
      slogf("[NTP] time synced: %s", buf);
      return;
    }
    waited += 2000;
    slog("[NTP] waiting for time sync...");
  }
  slog("[NTP] time sync failed / timed out");
}


// ---------------------- LOG helpers -------------------------
void webBroadcastSafe(const String& s) {
  String tmp = s;
  if (webSocket && webSocket->connectedClients() > 0) if (webSocket) webSocket->broadcastTXT(tmp);
}

void logToWebAndFile(const String& s) {
  // NOTE: we intentionally do NOT write logs to SPIFFS to avoid flash wear.
  // We keep sending logs to websocket (RAM) only.
  String tmp = s;

  // send to WebSocket if connected
  if (webSocket && webSocket->connectedClients() > 0) {
    webSocket->broadcastTXT(tmp);
  }

  // also print to serial for local debugging
  Serial.println(tmp);
}


void slog(const char* s) {
  logToWebAndFile(String(s));
}

void slogf(const char* fmt, ...) {
  char buf[512];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof(buf), fmt, ap);
  va_end(ap);
  logToWebAndFile(String(buf));
}

void slogHexTag(const char* tag, const uint8_t* data, size_t len) {
  char buf[1024];
  int p = snprintf(buf, sizeof(buf), "[%s] ", tag);
  for (size_t i = 0; i < len && p < (int)sizeof(buf) - 4; ++i) {
    p += snprintf(buf + p, sizeof(buf) - p, "%02X ", data[i]);
  }
  buf[sizeof(buf) - 1] = 0;
  time_t now = time(nullptr);
  char ts[64] = "";
  if (now != (time_t)0) {
    struct tm tmbuf;
    localtime_r(&now, &tmbuf);
    strftime(ts, sizeof(ts), "%Y-%m-%d %H:%M:%S", &tmbuf);
  }
  String out = String("[") + String(ts) + "] " + String(buf);
  logToWebAndFile(out);
}


// ------------------------ UTIL ------------------------------
std::vector<uint8_t> hexToBytes(const String& hex) {
  std::vector<uint8_t> out;
  String s = hex;
  s.replace(" ", "");
  s.toUpperCase();
  for (int i = 0; i + 1 < (int)s.length(); i += 2) {
    char a = s[i], b = s[i + 1];
    uint8_t hi = (a >= '0' && a <= '9') ? a - '0' : a - 'A' + 10;
    uint8_t lo = (b >= '0' && b <= '9') ? b - '0' : b - 'A' + 10;
    out.push_back((hi << 4) | lo);
  }
  return out;
}

String bytesToHexLine(const uint8_t* data, size_t len) {
  String s = "";
  for (size_t i = 0; i < len; ++i) {
    if (i) s += ' ';
    char tmp[4];
    sprintf(tmp, "%02X", data[i]);
    s += String(tmp);
  }
  return s;
}


// ----------------- BLE: Peripheral callbacks ----------------
class PeripheralCallbacks : public NimBLECharacteristicCallbacks {
  void onRead(NimBLECharacteristic* pChar) override {
    logToWebAndFile(String("[APP read] fff1 requested"));
    if (batteryConnected && pRemoteChar1 && pRemoteChar1->canRead()) {
      try {
        std::string rv = pRemoteChar1->readValue();
        if (!rv.empty()) {
          pPeripheralChar1->setValue((const uint8_t*)rv.data(), rv.size());
          slogHexTag("Reply->APP (fff1)", (const uint8_t*)rv.data(), rv.size());
        }
      } catch (...) { logToWebAndFile(String("[APP read] exception during remote read")); }
    } else {
      logToWebAndFile(String("[APP read] battery not connected or remote fff1 not readable"));
    }
  }

  void onWrite(NimBLECharacteristic* pChar) override {
    std::string val = pChar->getValue();
    if (val.size() == 0) return;
    const uint8_t* data = (const uint8_t*)val.data();
    size_t len = val.size();

    if (pythonDriven) {
      slogHexTag("APP->ESP ignored (python-driven)", data, len);
      return;
    }

    if (pChar == pPeripheralChar2) {
      slogHexTag("APP->ESP fff2", data, len);
      if (batteryConnected && pRemoteChar2) {
        bool ok = false;
        for (int r = 0; r < WRITE_RETRY_COUNT; ++r) {
          ok = pRemoteChar2->writeValue(data, len, false);
          if (ok) break;
          delay(WRITE_RETRY_DELAY_MS);
        }
        if (ok) slogHexTag("ESP->BATTERY fff2", data, len);
        else {
          if (writeQueue.size() < MAX_QUEUE) writeQueue.push_back({ std::vector<uint8_t>(data, data + len) });
          logToWebAndFile(String("[APP->ESP] fff2 queued"));
        }
      } else {
        if (writeQueue.size() < MAX_QUEUE) writeQueue.push_back({ std::vector<uint8_t>(data, data + len) });
        logToWebAndFile(String("[APP->ESP] fff2 queued (battery not connected)"));
      }
    } else if (pChar == pPeripheralChar1) {
      slogHexTag("APP->ESP fff1 (write)", data, len);
      if (batteryConnected && pRemoteChar1) {
        bool ok = false;
        for (int r = 0; r < WRITE_RETRY_COUNT; ++r) {
          ok = pRemoteChar1->writeValue(data, len, false);
          if (ok) break;
          delay(WRITE_RETRY_DELAY_MS);
        }
        if (ok) slogHexTag("ESP->BATTERY fff1", data, len);
        else {
          if (writeQueue.size() < MAX_QUEUE) writeQueue.push_back({ std::vector<uint8_t>(data, data + len) });
          logToWebAndFile(String("[APP->ESP] fff1 queued"));
        }
      } else {
        if (writeQueue.size() < MAX_QUEUE) writeQueue.push_back({ std::vector<uint8_t>(data, data + len) });
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

    // When app connects in proxy mode: ensure we're connected to battery and push initial data to app
    if (!pythonDriven) {
      if (!batteryConnected && TARGET_BATTERY_ADDR.length() > 0) {
        connectToBatteryByAddr(std::string(TARGET_BATTERY_ADDR.c_str()));
      } else {
        // try to push current remote fff1 value immediately if available
        if (batteryConnected && pRemoteChar1 && pRemoteChar1->canRead() && pPeripheralChar1) {
          try {
            std::string rv = pRemoteChar1->readValue();
            if (!rv.empty()) {
              pPeripheralChar1->setValue((const uint8_t*)rv.data(), rv.size());
              pPeripheralChar1->notify(true);
              slogHexTag("InitialPush->APP (fff1)", (const uint8_t*)rv.data(), rv.size());
            }
          } catch (...) {}
        }
      }
    } else {
      // If we're in python-driven and an APP somehow connected, politely log and we'll ignore writes
      slog("[APP] connected while in python-driven mode (writes will be ignored)");
    }
  }
  void onDisconnect(NimBLEServer* srv) override {
    appConnected = false;
    logToWebAndFile(String("[APP] disconnected from ESP peripheral"));
  }
};


// ------------------ BLE: Central callbacks ------------------
class ClientCbs : public NimBLEClientCallbacks {
  void onConnect(NimBLEClient* cli) override {
    batteryConnected = true;
    logToWebAndFile(String("[ESP] connected to real battery"));
  }
  void onDisconnect(NimBLEClient* cli) override {
    batteryConnected = false;
    logToWebAndFile(String("[ESP] disconnected from real battery"));
    pRemoteChar1 = nullptr;
    pRemoteChar2 = nullptr;
    if (pClient) {
      NimBLEDevice::deleteClient(pClient);
      pClient = nullptr;
    }
  }
};

// battery notify callback
static void batteryNotifyCB(NimBLERemoteCharacteristic* rc, uint8_t* data, size_t len, bool isNotify) {
  slogHexTag("BATTERY->ESP (notify)", data, len);

  // Forward to APP if proxy mode
  if (!pythonDriven && appConnected && pPeripheralChar1) {
    pPeripheralChar1->setValue(data, len);
    // use notify (and INDICATE supported by characteristic definition)
    pPeripheralChar1->notify(true);
    slogHexTag("ESP->APP (notify)", data, len);
  }

  // Always broadcast to websocket clients (for logging)
  if (webSocket && webSocket->connectedClients() > 0) {
    String js = String("{\"notify\":\"") + bytesToHexLine(data, len) + String("\"}");
    String tmp = js;
    if (webSocket) webSocket->broadcastTXT(tmp);
  }
}

// Scan callbacks: capture serviceData if present to mimic battery advert
class ScanCbs : public NimBLEAdvertisedDeviceCallbacks {
  void onResult(NimBLEAdvertisedDevice* adv) override {
    std::string sd = adv->getServiceData();
    String msg = String("[SCAN] ") + adv->getAddress().toString().c_str();
    if (sd.size() > 0) {
      String hex = "";
      for (size_t i = 0; i < sd.size(); ++i) {
        char b[4];
        sprintf(b, "%02X", (uint8_t)sd[i]);
        hex += String(b);
      }
      msg += String(" svcdata=") + hex;
      cachedSvcData = sd;  // save last seen serviceData (best-effort)
    }
    logToWebAndFile(msg);
  }
};


// ------------------- Connect helper -------------------------
bool connectToBatteryByAddr(const std::string& addrStr) {
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

  // initial read from remote fff1 if readable — push to APP immediately (help app accept device)
  if (pRemoteChar1 && pRemoteChar1->canRead()) {
    try {
      std::string rv = pRemoteChar1->readValue();
      if (!rv.empty()) {
        slogHexTag("Initial read fff1", (const uint8_t*)rv.data(), rv.size());
        if (!pythonDriven && appConnected && pPeripheralChar1) {
          pPeripheralChar1->setValue((const uint8_t*)rv.data(), rv.size());
          pPeripheralChar1->notify(true);
          logToWebAndFile(String("[ESP] initial battery value pushed to APP"));
        }
      }
    } catch (...) { logToWebAndFile(String("[ESP] exception during initial read")); }
  }

  // If we captured serviceData from scan, apply it to our advertise so APP sees expected svcdata
  if (!cachedSvcData.empty()) {
    NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
    adv->setServiceData(SERVICE_UUID, cachedSvcData);  // best-effort; may be ignored by some stacks
    slogf("[ADVERT] applied cached svcdata to advert (len=%u)", (unsigned)cachedSvcData.size());
  }

  return true;
}


// ------------------- process queued writes ------------------
void processWriteQueueOnce() {
  if (!batteryConnected || !pRemoteChar2) return;
  if (writeQueue.empty()) return;

  auto& qw = writeQueue.front();
  bool ok = false;
  for (int r = 0; r < WRITE_RETRY_COUNT; ++r) {
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


// ---------------------- Peripheral setup --------------------
void setupPeripheral() {
  logToWebAndFile(String("[SETUP] peripheral start"));

  NimBLEDevice::setPower(ESP_PWR_LVL_P9);
  pServer = NimBLEDevice::createServer();
  pServer->setCallbacks(new ServerCbs());

  NimBLEService* svc = pServer->createService(SERVICE_UUID);

  // IMPORTANT: include INDICATE for compatibility with official apps
  pPeripheralChar1 = svc->createCharacteristic(
    CHAR1_UUID,
    NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::NOTIFY | NIMBLE_PROPERTY::INDICATE);

  pPeripheralChar2 = svc->createCharacteristic(
    CHAR2_UUID,
    NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR);

  static PeripheralCallbacks perCb;
  pPeripheralChar1->setCallbacks(&perCb);
  pPeripheralChar2->setCallbacks(&perCb);

  svc->start();

  NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->addServiceUUID(SERVICE_UUID);
  adv->setName(ADVERT_NAME);

  // prefer faster advertise interval (best-effort)
  adv->setMinPreferred(0x06);  // ~7.5ms
  adv->setMaxPreferred(0x06);

  // if we previously captured serviceData, set it
  if (!cachedSvcData.empty()) {
    adv->setServiceData(SERVICE_UUID, cachedSvcData);
  }

  NimBLEDevice::startAdvertising();
  logToWebAndFile(String("[SETUP] peripheral advertising started"));
}


// -------------------- mode application ----------------------
void applyMode() {
  // Apply advertising / app behavior based on pythonDriven flag.
  if (pythonDriven) {
    // Stop advertising so official app will not connect (or will disconnect).
    NimBLEDevice::stopAdvertising();
    String msg = String("[MODE] Applied python-driven: advertising stopped, APP writes will be ignored");
    webBroadcastSafe(msg);
    logToWebAndFile(msg);
    // If an app was connected, we can't reliably call server disconnect in all NimBLE builds,
    // so just set appConnected false and log a note. App will eventually notice disconnect if advertising stopped.
    if (appConnected) {
      appConnected = false;
      logToWebAndFile(String("[MODE] Forcing appConnected=false (python-driven)"));
    }
  } else {
    // Proxy mode: ensure advertising is running so APP can connect
    NimBLEDevice::startAdvertising();
    String msg = String("[MODE] Applied proxy: advertising started, APP will be served");
    webBroadcastSafe(msg);
    logToWebAndFile(msg);
    // If battery connected and remote fff1 readable, try to push initial value to APP when it connects.
  }
}


// -------------------- Websocket handler ---------------------
void handle_ws_command(uint8_t num, const String& cmd) {
  if (cmd == "scan") {
    NimBLEScan* pScan = NimBLEDevice::getScan();
    pScan->setAdvertisedDeviceCallbacks(new ScanCbs());
    pScan->setActiveScan(true);
    pScan->start(6, false);
    logToWebAndFile(String("[WS] scan requested"));
    return;
  }
  if (cmd.startsWith("connect ")) {
    String addr = cmd.substring(8);
    addr.trim();
    if (addr.length() == 0) {
      logToWebAndFile(String("[WS] connect: empty addr"));
      return;
    }
    TARGET_BATTERY_ADDR = addr;
    logToWebAndFile(String("[WS] connect requested: ") + TARGET_BATTERY_ADDR);
    connectToBatteryByAddr(std::string(TARGET_BATTERY_ADDR.c_str()));
    return;
  }
  if (cmd.startsWith("set_mode ")) {
    String arg = cmd.substring(9);
    arg.trim();
    bool newMode = (arg == "python-driven");
    pythonDriven = newMode;
    saveModeToSPIFFS();
    applyMode();
    logToWebAndFile(String("[WS] mode set: ") + (pythonDriven ? "python-driven" : "proxy"));
    return;
  }
  if (cmd.startsWith("save_target ")) {
    String arg = cmd.substring(12);
    arg.trim();
    TARGET_BATTERY_ADDR = arg;
    saveTargetToSPIFFS();
    logToWebAndFile(String("[WS] saved target: ") + TARGET_BATTERY_ADDR);
    return;
  }

  // JSON-like cmd support: {"cmd":"D2 03 ..."} or {"cmd":"<hex>"}
  if (cmd.startsWith("{") && cmd.indexOf("cmd") >= 0) {
    int idx = cmd.indexOf("cmd");
    int colon = cmd.indexOf(':', idx);
    int q1 = cmd.indexOf('"', colon);
    int q2 = cmd.indexOf('"', q1 + 1);
    if (q1 > 0 && q2 > q1) {
      String hexStr = cmd.substring(q1 + 1, q2);
      std::vector<uint8_t> v = hexToBytes(hexStr);
      if (v.size() > 0) {
        if (batteryConnected && pRemoteChar2) {
          bool ok = false;
          for (int r = 0; r < WRITE_RETRY_COUNT; ++r) {
            ok = pRemoteChar2->writeValue(v.data(), v.size(), false);
            if (ok) break;
            delay(WRITE_RETRY_DELAY_MS);
          }
          if (ok) {
            slogHexTag("WS->BATTERY fff2", v.data(), v.size());
            String ack = String("{\"reply\":\"") + hexStr + String("\"}");
            if (webSocket) webSocket->sendTXT(num, ack);
          } else {
            if (writeQueue.size() < MAX_QUEUE) writeQueue.push_back({ v });
            logToWebAndFile(String("[WS] write failed - queued"));
          }
        } else {
          if (writeQueue.size() < MAX_QUEUE) writeQueue.push_back({ v });
          logToWebAndFile(String("[WS] battery not connected - queued"));
        }
        return;
      }
    }
  }

  logToWebAndFile(String("[WS] unknown: ") + cmd);
}


// ---------------------- Websocket event ---------------------
void webSocketEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t length) {
  if (type == WStype_TEXT) {
    String cmd = String((char*)payload);
    slogf("WS cmd: %s", cmd.c_str());
    handle_ws_command(num, cmd);
  } 
  else if (type == WStype_CONNECTED) {
    IPAddress ip = webSocket ? webSocket->remoteIP(num) : IPAddress(0,0,0,0);
    slogf("WS client %u connected from %s", (unsigned)num, ip.toString().c_str());
  } 
  else if (type == WStype_DISCONNECTED) {
    slogf("WS client %u disconnected", (unsigned)num);
  }
}



// ======================== WEB UI ============================
//
// ------------------------ HEADER ----------------------------
String htmlHeader() {
  return R"(
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { background: #121212; color: #eee; font-family: sans-serif; padding: 10px; }
nav a { display:inline-block; margin:5px; padding:5px 10px; color:#eee; text-decoration:none; background:#1f1f1f; border-radius:4px;}
nav a:hover { background:#333;}
input, select { background:#222; color:#eee; border:1px solid #555; padding:4px; margin:2px;}
input[type=submit], button { background:#1f1f1f; color:#eee; border:none; padding:6px 12px; cursor:pointer;}
input[type=submit]:hover, button:hover { background:#333;}
pre { background:#1f1f1f; padding:8px; border-radius:4px; overflow:auto;}
</style>
)";
}


// --------------------- NAVIGATION MENU ----------------------
String makeNav() {
  String nav = "<nav>";
  if (loggedIn) {
    nav += "<a href='/battery'>Battery Settings</a>";
    nav += "<a href='/wifi'>WiFi Setup</a>";
    nav += "<a href='/ip'>IP Settings</a>";
    nav += "<a href='/admin'>Admin</a>";
    nav += "<a href='/logout'>Logout</a>";
  } else {
    nav += "<a href='/login'>Login</a>";
  }
  nav += "</nav>";
  return nav;
}


// ======================== PAGES =============================
//
// ----------------------- AUTH PAGE --------------------------
void handleLoginPage() {
  String msg = "";
  if (httpServer.method() == HTTP_POST) {
    String u = httpServer.arg("user");
    String p = httpServer.arg("pass");
    if (u == "admin" && p == admin_pass) {
      loggedIn = true;
      httpServer.sendHeader("Location", "/", true);
      httpServer.send(302, "text/plain", "");
      return;
    } else {
      msg = "<p style='color:red;text-align:center;'>Wrong username/password</p>";
    }
  }

  String page = "<html>" + htmlHeader() + "<body style='display:flex;justify-content:center;align-items:center;height:100vh;'>"
                                          "<div style='background:#121212;padding:20px;border-radius:8px;box-shadow:0 0 10px rgba(0,0,0,0.5);min-width:300px;'>"
                                          "<h2 style='text-align:center;margin-bottom:15px;'>Ritar BT Gate</h2>"
                + msg + "<form method='POST' style='display:flex;flex-direction:column;gap:10px;'>"
                        "<div style='display:flex;align-items:center;'>"
                        "<span style='display:inline-block;width:80px;'>Username:</span>"
                        "<input name='user' style='flex:1;background:#222;color:#eee;border:1px solid #555;padding:4px;'>"
                        "</div>"
                        "<div style='display:flex;align-items:center;'>"
                        "<span style='display:inline-block;width:80px;'>Password:</span>"
                        "<input type='password' name='pass' style='flex:1;background:#222;color:#eee;border:1px solid #555;padding:4px;'>"
                        "</div>"
                        "<input type='submit' value='Login' style='background:#1f1f1f;color:#eee;border:none;padding:6px 12px;cursor:pointer;'>"
                        "</form>"
                        "</div>"
                        "</body></html>";

  httpServer.send(200, "text/html", page);
}

bool requireLogin() {
  if (!loggedIn) {
    httpServer.sendHeader("Location", "/login", true);
    httpServer.send(302, "text/plain", "");
    return false;
  }
  return true;
}

void handleLogout() {
  loggedIn = false;
  httpServer.sendHeader("Location", "/", true);
  httpServer.send(302, "text/plain", "");
}


// ---------------------- BATTERY PAGE ------------------------
void handleBattery() {
  if (!requireLogin()) return;

  String page;
  page = "<html>";
  page += htmlHeader();
  page += "<body>";
  page += "<h2>Master Battery Settings</h2>";
  page += makeNav();

  page += R"rawliteral(
  <div style="max-width:700px;margin-top:10px;">

    <!-- Row 1: Toggle Mode + Mode display -->
    <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:12px;">
      <button id="btnToggle">Toggle Mode</button>
      <span>Mode: <span id="mode" style="padding:2px 6px;border-radius:4px;background:#888;color:#fff;">loading...</span></span>
    </div>

    <!-- Row 2: Scan + MAC input -->
    <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:12px;">
      <button id="btnScan">Scan</button>
      <input id="connectAddr" placeholder="MAC (AC:..)" style="width:180px;">
    </div>

    <!-- Row 3: Connect + Save Target -->
    <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:8px;">
      <button id="btnConnect">Connect</button>
      <button id="btnSaveTarget">Save Target</button>
    </div>

    <!-- Log Console -->
    <pre id="log" style="background:#111;color:#0f0;padding:8px;height:320px;overflow:auto;white-space:pre-wrap">Connecting...</pre>
  </div>

  <script>
  // WebSocket + log
  let ws = new WebSocket('ws://' + location.hostname + ':%WS_PORT%/');
  let modeSpan = document.getElementById('mode');
  let log = document.getElementById('log');

  function append(s){
    log.textContent += s + '\n'; // add real newline
    log.scrollTop = log.scrollHeight;
  }

  // Function to set friendly text + color for mode
  function setModeVisual(m){
    let displayText = m;
    if (m === 'proxy') { displayText = 'Native APP BluetoothLi'; modeSpan.style.background = '#0a0'; modeSpan.style.color = '#000'; }
    else if (m === 'python-driven') { displayText = 'Homeassistant Addon Ritar-BMS'; modeSpan.style.background = '#aa0'; modeSpan.style.color = '#000'; }
    else if (m.startsWith('pending:')) { displayText = 'pending…'; modeSpan.style.background = '#888'; modeSpan.style.color = '#fff'; }
    else if (m === 'python-driven (RAM)') { displayText = 'Homeassistant Addon Ritar-BMS (RAM)'; modeSpan.style.background = '#f90'; modeSpan.style.color = '#000'; }
    else if (m === 'proxy (RAM)') { displayText = 'Native APP BluetoothLi (RAM)'; modeSpan.style.background = '#5f5'; modeSpan.style.color = '#000'; }
    else { displayText = m; modeSpan.style.background = '#888'; modeSpan.style.color = '#fff'; }
    modeSpan.textContent = displayText;
  }

  ws.onopen = ()=>{
    append('[ws] connected');
    fetch('/mode').then(r=>r.text()).then(t=>setModeVisual(t));
    fetch('/target').then(r=>r.text()).then(t=>{ document.getElementById('connectAddr').value = t; });
  };

  ws.onmessage = (evt)=>{
    append(evt.data); // real line breaks from server are preserved

    if (evt.data.includes('[MODE] Saved mode: proxy')) setModeVisual('proxy');
    else if (evt.data.includes('[MODE] Saved mode: python-driven')) setModeVisual('python-driven');
    else if (evt.data.includes('[MODE] Persist failed - mode in RAM')) {
      if (evt.data.includes('python-driven')) setModeVisual('python-driven (RAM)');
      else setModeVisual('proxy (RAM)');
    }
    else if (evt.data.startsWith('[UI] pending:')) {
      let parts = evt.data.split(':');
      if (parts.length >= 2) setModeVisual('pending:' + parts[1].trim());
    }
  };

  document.getElementById('btnToggle').onclick = ()=>{
    let newMode = (modeSpan.textContent.startsWith('Native APP') || modeSpan.textContent.startsWith('Native APP')) ? 'python-driven' : 'proxy';
    ws.send('set_mode ' + newMode);
    setModeVisual('pending:' + newMode);
  };
  document.getElementById('btnScan').onclick = ()=>{ ws.send('scan'); };
  document.getElementById('btnConnect').onclick = ()=>{ let a=document.getElementById('connectAddr').value.trim(); if(a) ws.send('connect '+a); };
  document.getElementById('btnSaveTarget').onclick = ()=>{ let a=document.getElementById('connectAddr').value.trim(); if(a){ ws.send('save_target '+a); append('[UI] save_target -> '+a); } };
  </script>
  )rawliteral";

  page += "</body></html>";

  page.replace("%WS_PORT%", String(websocket_port));
  httpServer.send(200, "text/html", page);
}

// Return current device work mode ("proxy" for native APP or "python-driven" for Homeassistant addon)
void handleGetMode() {
  if (!requireLogin()) return;
  httpServer.send(200, "text/plain", pythonDriven ? "python-driven" : "proxy");
}

// Return current master battery MAC address
void handleGetTarget() {
  if (!requireLogin()) return;
  httpServer.send(200, "text/plain", TARGET_BATTERY_ADDR);
}


// ------------------------ WIFI PAGE -------------------------
void handleWiFiPage() {
  if (!requireLogin()) return;

  String currentSSID = WiFi.SSID();
  String currentIP = WiFi.localIP().toString();

  // generate SSID list from last scan
  String networkList = "";
  for (int i = 0; i < scannedCount; ++i) {
    networkList += "<option value='" + scannedNetworks[i].ssid + "'>" +
                   scannedNetworks[i].ssid + " (RSSI: " + String(scannedNetworks[i].rssi) + "dBm" +
                   (scannedNetworks[i].secure ? ", Secured" : ", Open") + ")</option>";
  }

  String html = "<html>" + htmlHeader() + "<body>"
                "<h2>WiFi Setup</h2>"
                + makeNav() +
                "<p>Currently connected: <b>" + (currentSSID.length() ? currentSSID : "Not connected") + "</b>";
  if(currentSSID.length()) html += " (IP: " + currentIP + ")";
  html += "</p>"

          // SSID list form
          "<h2>Available networks:</h2>"
          "<form action='/wificonn' method='POST'>"
          "<select name='ssid'>" + networkList + "</select><br>"
          "Password:<br><input type='password' name='pass'><br><br>"
          "<input type='submit' value='Connect'>"
          "</form><hr>"
          
          // manual connection form
          "<h2>Manual Connection:</h2>"
          "<form action='/wifisave' method='POST'>"
          "WiFi SSID:<br><input name='ssid' value='" + wifi_ssid + "'><br>"
          "Password:<br><input type='password' name='pass' value='" + wifi_pass + "'><br><br>"
          "<input type='submit' value='Save'>"
          "</form>"

          "</body></html>";

  httpServer.send(200, "text/html", html);
}

void handleWiFiSave() {
  if (!requireLogin()) return;
  String ssid = httpServer.arg("ssid");
  String pass = httpServer.arg("pass");
  saveWiFi(ssid, pass);
  httpServer.send(200, "text/html", "Saved! Rebooting...");
  delay(500);
  ESP.restart();
}

void handleWiFiConnect() {
  if (!requireLogin()) return;

  String ssid = httpServer.arg("ssid");
  String pass = httpServer.arg("pass");

  if(ssid.length() == 0){
    httpServer.send(200, "text/html", "SSID not provided!");
    return;
  }

  saveWiFi(ssid, pass);  // save for restart
  httpServer.send(200, "text/html", "Connecting to " + ssid + "... Rebooting...");
  delay(500);
  ESP.restart();
}


// ------------------------- IP PAGE --------------------------
void handleIPPage() {
  if (!requireLogin()) return;
  IPAddress curIP = WiFi.localIP();
  IPAddress curMask = WiFi.subnetMask();
  IPAddress curGW = WiFi.gatewayIP();
  String ipField = useStaticIP ? ip_addr : curIP.toString();
  String maskField = useStaticIP ? netmask : curMask.toString();
  String gwField = useStaticIP ? gateway : curGW.toString();
  httpServer.send(200, "text/html", "<html>" + htmlHeader() + "<body>"
                                                              "<h2>IP Settings</h2>"
                                      + makeNav() + "<p>Current IP: " + curIP.toString() + "</p>"
                                                                                           "<form action='/ipsave' method='POST'>"
                                                                                           "Use Static IP: <input type='checkbox' name='useStatic' "
                                      + String(useStaticIP ? "checked" : "") + "><br>"
                                                                               "IP: <input name='ip' value='"
                                      + ipField + "'><br>"
                                                  "Netmask: <input name='mask' value='"
                                      + maskField + "'><br>"
                                                    "Gateway: <input name='gw' value='"
                                      + gwField + "'><br><br>"
                                                  "<input type='submit' value='Apply'>"
                                                  "</form>"
                                                  "</body></html>");
}

// Save IP mode - DHCP or manual
void handleIPSave() {
  if (!requireLogin()) return;
  useStaticIP = httpServer.hasArg("useStatic");
  ip_addr = httpServer.arg("ip");
  netmask = httpServer.arg("mask");
  gateway = httpServer.arg("gw");
  saveIPSettings();
  httpServer.send(200, "text/html", "Saved! Rebooting...");
  delay(500);
  ESP.restart();
}


// ------------------------ ADMIN PAGE ------------------------
void handleAdminPage() {
  if (!requireLogin()) return;
  String msg = "";

  if (httpServer.method() == HTTP_POST) {
    // ------------------ password handling -------------------
    String p1 = httpServer.arg("pass1");
    String p2 = httpServer.arg("pass2");
    if (p1.length() > 0 && p1 == p2) {
      handleSaveAdminPass(p1);
      msg = "<p style='color:green'>Password saved!</p>";
    } else if (p1 != p2 && (p1.length() > 0 || p2.length() > 0)) {
      // only show mismatch if user tried to change password
      msg = "<p style='color:red'>Passwords do not match!</p>";
    }

    // --------------- time settings handling  ----------------
    // If the admin form submitted a 'tz' field — update time settings.
    if (httpServer.hasArg("tz")) {
      // tz value is expected in hours (e.g. "2" for UTC+2); convert to seconds
      long tzHours = httpServer.arg("tz").toInt();
      GMT_OFFSET_SEC = tzHours * 3600L;

      // dst_flag checkbox present means DST enabled
      if (httpServer.hasArg("dst_flag")) {
        DAYLIGHT_OFFSET_SEC = 3600; // +1 hour DST
      } else {
        DAYLIGHT_OFFSET_SEC = 0;
      }

      saveTimeSettings();
      startNtpAndSync();

      msg += "<p style='color:green'>Time settings updated!</p>";
    }
  }

  // ------------------ current date and time------------------
  struct tm timeinfo;
  char timeBuf[64] = "";
  if (getLocalTime(&timeinfo)) {
    strftime(timeBuf, sizeof(timeBuf), "%Y-%m-%d %H:%M:%S", &timeinfo);
  }

  String html = "<html>" + htmlHeader() + "<body>"
                "<h2>BT Gate Admin Settings</h2>"
                + makeNav() + msg + "<form method='POST'>"
                // Admin password change section
                "<hr><h2>Admin Password</h2>"
                "New password:<br><input type='password' name='pass1'><br>"
                "Confirm password:<br><input type='password' name='pass2'><br><br>"
                "<input type='submit' value='Save'></form>"
                "<hr>"

                // websocket / API tcp port 
                "<h2>API Settings</h2>"
                "<form method='POST' action='/savewsport'>"
                "TCP Port:<br><input name='ws_port' value='" + String(websocket_port) + "'><br><br>"
                "<input type='submit' value='Save'>"
                "</form><hr>"

                // Time settings block
                "<h2>Time Settings</h2>"
                "<p>Current time: " + String(timeBuf) + "</p>"
                "<form method='POST'>"
                "Timezone (hours offset from UTC):<br>"
                "<select name='tz'>"
                "<option value='-12' " + String(GMT_OFFSET_SEC == -12L*3600L ? "selected" : "") + ">UTC-12</option>"
                "<option value='-11' " + String(GMT_OFFSET_SEC == -11L*3600L ? "selected" : "") + ">UTC-11</option>"
                "<option value='-10' " + String(GMT_OFFSET_SEC == -10L*3600L ? "selected" : "") + ">UTC-10</option>"
                "<option value='-9'  " + String(GMT_OFFSET_SEC == -9L*3600L  ? "selected" : "") + ">UTC-9</option>"
                "<option value='-8'  " + String(GMT_OFFSET_SEC == -8L*3600L  ? "selected" : "") + ">UTC-8</option>"
                "<option value='-7'  " + String(GMT_OFFSET_SEC == -7L*3600L  ? "selected" : "") + ">UTC-7</option>"
                "<option value='-6'  " + String(GMT_OFFSET_SEC == -6L*3600L  ? "selected" : "") + ">UTC-6</option>"
                "<option value='-5'  " + String(GMT_OFFSET_SEC == -5L*3600L  ? "selected" : "") + ">UTC-5</option>"
                "<option value='-4'  " + String(GMT_OFFSET_SEC == -4L*3600L  ? "selected" : "") + ">UTC-4</option>"
                "<option value='-3'  " + String(GMT_OFFSET_SEC == -3L*3600L  ? "selected" : "") + ">UTC-3</option>"
                "<option value='-2'  " + String(GMT_OFFSET_SEC == -2L*3600L  ? "selected" : "") + ">UTC-2</option>"
                "<option value='-1'  " + String(GMT_OFFSET_SEC == -1L*3600L  ? "selected" : "") + ">UTC-1</option>"
                "<option value='0'   " + String(GMT_OFFSET_SEC == 0L         ? "selected" : "") + ">UTC+0</option>"
                "<option value='1'   " + String(GMT_OFFSET_SEC == 1L*3600L   ? "selected" : "") + ">UTC+1</option>"
                "<option value='2'   " + String(GMT_OFFSET_SEC == 2L*3600L   ? "selected" : "") + ">UTC+2 (Kyiv)</option>"
                "<option value='3'   " + String(GMT_OFFSET_SEC == 3L*3600L   ? "selected" : "") + ">UTC+3</option>"
                "<option value='4'   " + String(GMT_OFFSET_SEC == 4L*3600L   ? "selected" : "") + ">UTC+4</option>"
                "<option value='5'   " + String(GMT_OFFSET_SEC == 5L*3600L   ? "selected" : "") + ">UTC+5</option>"
                "<option value='6'   " + String(GMT_OFFSET_SEC == 6L*3600L   ? "selected" : "") + ">UTC+6</option>"
                "<option value='7'   " + String(GMT_OFFSET_SEC == 7L*3600L   ? "selected" : "") + ">UTC+7</option>"
                "<option value='8'   " + String(GMT_OFFSET_SEC == 8L*3600L   ? "selected" : "") + ">UTC+8</option>"
                "<option value='9'   " + String(GMT_OFFSET_SEC == 9L*3600L   ? "selected" : "") + ">UTC+9</option>"
                "<option value='10'  " + String(GMT_OFFSET_SEC == 10L*3600L  ? "selected" : "") + ">UTC+10</option>"
                "<option value='11'  " + String(GMT_OFFSET_SEC == 11L*3600L  ? "selected" : "") + ">UTC+11</option>"
                "<option value='12'  " + String(GMT_OFFSET_SEC == 12L*3600L  ? "selected" : "") + ">UTC+12</option>"
                "</select><br><br>"

                // DST checkbox (checked if DAYLIGHT_OFFSET_SEC != 0)
                "<label><input type='checkbox' name='dst_flag' value='1' " + String(DAYLIGHT_OFFSET_SEC != 0 ? "checked" : "") + "> Use DST (+1h)</label><br><br>"

                "<input type='submit' value='Save Time Settings'>"
                "</form>"
                "<hr>"

                // Firmware update section
                "<h2>Firmware Update</h2>"
                "<p>Current Version: " FIRMWARE_VERSION "</p>"
                "<a href='/firmware'><button style='padding:8px 16px;'>Firmware Update</button></a>"
                "<hr>"

                // Buttons RESET and Reboot in one line
                "<div style='display:flex;gap:8px;'>"
                "<button style='background:#b71c1c;color:#fff;padding:8px 16px;' onclick='fetch(\"/reset\").then(()=>location.reload())'>RESET WIFI SETTINGS | ADMIN PASSWORD</button>"
                "<button style='background:#b71c1c;color:#fff;padding:8px 16px;' onclick='fetch(\"/reboot\").then(()=>alert(\"Rebooting device...\"))'>Reboot Device</button>"
                "</div>"
                "</body></html>";

  httpServer.send(200, "text/html", html);
}


// admin password changer
void handleSaveAdminPass(const String &p) {
  pref.begin("wifi", false);
  pref.putString("admin", p);
  pref.end();
  admin_pass = p;
}

// websocket / api port save
void handleSaveWsPort() {
    if (!requireLogin()) return;

    uint16_t newPort = httpServer.arg("ws_port").toInt();
    if (newPort < 1 || newPort > 65535) newPort = 50501;

    saveWebsocketPort(newPort); // save to SPIFFS
    startWebSocket(newPort);    // restart WebSocket / api on new port

    // redirect to admin page
    httpServer.sendHeader("Location", "/admin"); // where to redirect
    httpServer.send(303);                        // 303 See Other
}



// device reset to factory defaults
void handleFactoryReset() {
  pref.begin("wifi", false);
  pref.clear();
  pref.end();
  admin_pass = DEFAULT_ADMIN;
  Serial.println("Wi-Fi settings and admin password cleared, restarting...");
  ESP.restart();
}

// device reboot
void handleReboot() {
  if (!requireLogin()) return;
  httpServer.send(200, "text/plain", "Rebooting...");
  delay(200);
  ESP.restart();
}


// ------------------- FIRMWARE UPDATE PAGE -------------------
void handleFirmwarePage() {
  if (!requireLogin()) return;

  String page = "<html>" + htmlHeader() +
                "<body style='display:flex;justify-content:center;align-items:center;height:100vh;background:#121212;color:#eee;'>"
                "<div style='background:#1e1e1e;padding:24px;border-radius:8px;box-shadow:0 0 10px rgba(0,0,0,0.5);min-width:320px;text-align:center;'>"
                "<h2 style='margin-bottom:15px;'>Firmware Update</h2>"
                "<p style='margin-bottom:10px;'>Current Version: " FIRMWARE_VERSION "</p>"
                "<form method='POST' action='/update' enctype='multipart/form-data' style='display:flex;flex-direction:column;gap:10px;'>"
                "<input type='file' name='firmware' style='background:#222;color:#eee;border:1px solid #555;padding:6px;border-radius:4px;'>"
                "<input type='submit' value='Upload & Update' "
                "style='background:#b71c1c;color:#fff;border:none;padding:8px;border-radius:4px;cursor:pointer;font-weight:bold;'>"
                "</form>"
                "<p style='font-size:12px;color:#aaa;margin-top:15px;'>Device will reboot automatically after update.</p>"
                "<hr style='margin:16px 0;border-color:#333;'>"
                "<a href='/admin'><button style='background:#333;color:#eee;padding:6px 12px;border:none;border-radius:4px;cursor:pointer;'>Back to Admin</button></a>"
                "</div></body></html>";

  httpServer.send(200, "text/html", page);
}

// firmware updater
void handleFirmwareUpdate() {
  if (!requireLogin()) return;
  HTTPUpload &upload = httpServer.upload();
  static size_t totalWritten = 0;

  switch (upload.status) {
    case UPLOAD_FILE_START:
      totalWritten = 0;
      Serial.printf("[FW UPDATE] start name=%s\n", upload.filename.c_str());

      if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {
        Serial.printf("[FW UPDATE] begin failed: %s (%u)\n", Update.errorString(), Update.getError());
        httpServer.send(500, "text/plain", "OTA begin failed");
        return;
      }
      break;

    case UPLOAD_FILE_WRITE: {
      size_t written = Update.write(upload.buf, upload.currentSize);
      totalWritten += written;
      Serial.printf("[FW UPDATE] chunk written=%u total=%u\n", (unsigned)written, (unsigned)totalWritten);
      break;
    }

    case UPLOAD_FILE_END:
      Serial.printf("[FW UPDATE] upload finished, totalWritten=%u\n", (unsigned)totalWritten);

      if (Update.end(true)) {
        Serial.println("[FW UPDATE] end OK -> rebooting");
        httpServer.send(200, "text/html", "<html><body>OK, rebooting...</body></html>");
        delay(1500);
        ESP.restart();
      } else {
        Serial.printf("[FW UPDATE] end failed: %s (%u)\n", Update.errorString(), Update.getError());
        httpServer.send(500, "text/plain", String("OTA end failed: ") + Update.errorString());
      }
      break;

    case UPLOAD_FILE_ABORTED:
      Serial.println("[FW UPDATE] aborted");
      Update.abort();
      break;
  }
}

// ===================== END OF SECTION =======================


// ----------------------- SETUP / LOOP -----------------------
unsigned long lastQueueMillis = 0;
unsigned long lastConnectMillis = 0;

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println();
  Serial.println("=== OTA Debug Info ===");
  Serial.printf("Sketch size: %u bytes\n", ESP.getSketchSize());
  Serial.printf("Free sketch space: %u bytes\n", ESP.getFreeSketchSpace());
  Serial.printf("Flash chip size: %u bytes\n", ESP.getFlashChipSize());
  Serial.printf("Flash chip speed: %u Hz\n", ESP.getFlashChipSpeed());
  Serial.printf("Flash chip mode: %u\n", ESP.getFlashChipMode());
  Serial.println("=======================");

  printPartitions();

  spiffsMounted = SPIFFS.begin(true);
  if (!spiffsMounted) logToWebAndFile(String("[SPIFFS] mount failed (will operate in RAM only)"));
  else logToWebAndFile(String("[SPIFFS] mounted"));

  loadModeFromSPIFFS();
  loadTargetFromSPIFFS();

  logToWebAndFile(String("[BOOT] Ritar Bluetooth Gate"));

  NimBLEDevice::init(ADVERT_NAME);
  NimBLEDevice::setSecurityAuth(false, false, false);

  setupPeripheral();

  // Apply mode after peripheral setup so advertising can be stopped/started correctly
  applyMode();

  loadWiFi();

  if (!loadWiFi() || !tryWiFi()) startAP();
  else Serial.println("WiFi Connected.");

  delay(1000);

  wifiScanFirstTime();

  loadTimeSettings();
  startNtpAndSync();

  loadWebsocketSettings();
  startWebSocket(websocket_port);


// Arduino IDE OTA for development purposes. Uncoment lines below :
//  ArduinoOTA.setPassword(OTA_PASSWORD);
//  ArduinoOTA.begin();
//  slog("[OTA] ready");


  httpServer.on("/", handleBattery);
  httpServer.on("/battery", handleBattery);
  httpServer.on("/mode", handleGetMode);
  httpServer.on("/target", handleGetTarget);
  httpServer.on("/login", handleLoginPage);
  httpServer.on("/logout", handleLogout);
  httpServer.on("/wifi", handleWiFiPage);
  httpServer.on("/wifisave", HTTP_POST, handleWiFiSave);
  httpServer.on("/wificonn", handleWiFiConnect);
  httpServer.on("/ip", handleIPPage);
  httpServer.on("/ipsave", HTTP_POST, handleIPSave);
  httpServer.on("/admin", handleAdminPage);
  httpServer.on("/savewsport", HTTP_POST, handleSaveWsPort);
  httpServer.on("/reset", handleFactoryReset);
  httpServer.on("/reboot", HTTP_GET, handleReboot);
  httpServer.on("/firmware", HTTP_GET, handleFirmwarePage);
  httpServer.on("/update", HTTP_POST, [](){}, handleFirmwareUpdate);


  httpServer.begin();


  lastConnectMillis = millis();
  lastQueueMillis = millis();

  if (TARGET_BATTERY_ADDR.length() > 0) {
    connectToBatteryByAddr(std::string(TARGET_BATTERY_ADDR.c_str()));
  }
  slogf("[MODE] Starting in %s mode", pythonDriven ? "python-driven" : "proxy");
}



void loop() {
// Arduino IDE OTA for development purposes. Uncoment line below :
//  ArduinoOTA.handle();

  wifiScanLoop();
  if (webSocket) webSocket->loop();
  httpServer.handleClient();

  // process queued write (throttled)
  if (millis() - lastQueueMillis > 50) {
    lastQueueMillis = millis();
    processWriteQueueOnce();
  }

  delay(5);
}

// ======================= END OF FILE ========================
