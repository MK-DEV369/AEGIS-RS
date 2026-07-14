#include <WiFi.h>
#include <esp_now.h>

// ─── Message Struct ────────────────────────────────────────────────────────────
// MUST match transmitter exactly
typedef struct struct_message {
    char text[250];
} struct_message;

struct_message incomingMessage;

// ─── Peer Config ───────────────────────────────────────────────────────────────
// Sender TX MAC: A0:B7:65:22:EB:14
uint8_t transmitterMAC[] = {0xA0, 0xB7, 0x65, 0x22, 0xEB, 0x14};

// ─── String Parsing Helpers ───────────────────────────────────────────────────
String getFieldValue(String data, String fieldPrefix) {
    int start = data.indexOf(fieldPrefix);
    if (start == -1) return "";
    int end = data.indexOf('|', start);
    if (end == -1) {
        return data.substring(start + fieldPrefix.length());
    }
    return data.substring(start + fieldPrefix.length(), end);
}

// ─── Internal handler ──────────────────────────────────────────────────────────
void handleAlert(const uint8_t *incomingData, int len)
{
    memcpy(&incomingMessage, incomingData, sizeof(incomingMessage));
    String payload = String(incomingMessage.text);

    // Default Fallbacks
    String typeStr = "RSU_ALERT";
    String severity = "low";
    double depth = 3.0;
    String lat = "12.924285";
    String lng = "77.499673";
    String source = "OBU_001";

    if (payload.startsWith("POTHOLE")) {
        String sev = getFieldValue(payload, "SEV:");
        sev.toLowerCase();
        if (sev.length() > 0) severity = sev;
        
        if (severity == "high") depth = 5.0;
        else if (severity == "critical") depth = 8.0;
        else if (severity == "medium") depth = 3.0;
        else depth = 1.0;

        String latVal = getFieldValue(payload, "LAT:");
        if (latVal.length() > 0) lat = latVal;

        String lngVal = getFieldValue(payload, "LNG:");
        if (lngVal.length() > 0) lng = lngVal;

        String srcVal = getFieldValue(payload, "SRC:");
        if (srcVal.length() > 0) {
            if (srcVal.startsWith("phone_") || srcVal.startsWith("OBU")) {
                source = "OBU_001";
            } else {
                source = srcVal;
            }
        }
    }
    else if (payload.startsWith("FOG")) {
        String lvl = getFieldValue(payload, "LVL:");
        lvl.toLowerCase();
        if (lvl.length() > 0) severity = lvl;
        depth = 0.0;

        String latVal = getFieldValue(payload, "LAT:");
        if (latVal.length() > 0) lat = latVal;

        String lngVal = getFieldValue(payload, "LNG:");
        if (lngVal.length() > 0) lng = lngVal;

        String srcVal = getFieldValue(payload, "SRC:");
        if (srcVal.length() > 0) {
            if (srcVal.startsWith("phone_") || srcVal.startsWith("OBU")) {
                source = "OBU_001";
            } else {
                source = srcVal;
            }
        }
    }

    // Output JSON string with trailing semicolon for the serial relay parser
    Serial.print("{\"type\":\"RSU_ALERT\",\"vehicle_id\":\"");
    Serial.print(source);
    Serial.print("\",\"lat\":");
    Serial.print(lat);
    Serial.print(",\"lng\":");
    Serial.print(lng);
    Serial.print(",\"severity\":\"");
    Serial.print(severity);
    Serial.print("\",\"speed\":0,\"depth_cm\":");
    Serial.print(depth, 1);
    Serial.print(",\"status\":\"DISSEMINATED\"};");
    Serial.println();
}

// ─── Receive Callback: Arduino Core v2 ────────────────────────────────────────
void OnDataRecvLegacy(const uint8_t *mac_addr, const uint8_t *incomingData, int len)
{
    handleAlert(incomingData, len);
}

// ─── Receive Callback: Arduino Core v3 ────────────────────────────────────────
#if defined(ESP_ARDUINO_VERSION) && ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
void OnDataRecv(const esp_now_recv_info *recv_info, const uint8_t *incomingData, int len)
{
    handleAlert(incomingData, len);
}
#endif

void setup() {
    Serial.begin(115200);
    
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) {
        Serial.println("Error initializing ESP-NOW");
        return;
    }
    
    Serial.println("==========================================");
    Serial.println("AEGIS-RS ESP-NOW Receiver Active");
    Serial.print("Board MAC Address: ");
    Serial.println(WiFi.macAddress());
    Serial.println("==========================================");

    // Register transmitter as peer
    esp_now_peer_info_t peerInfo;
    memset(&peerInfo, 0, sizeof(peerInfo));
    memcpy(peerInfo.peer_addr, transmitterMAC, 6);
    peerInfo.channel = 0;  
    peerInfo.encrypt = false;
    
    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
        Serial.println("Failed to add transmitter peer link");
    } else {
        Serial.println("Successfully added transmitter peer link");
    }

#if defined(ESP_ARDUINO_VERSION) && ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
    esp_now_register_recv_cb(OnDataRecv);
#else
    esp_now_register_recv_cb(OnDataRecvLegacy);
#endif
}

void loop() {
    delay(100);
}
