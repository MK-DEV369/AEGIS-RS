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

// ─── Receive Callback (Core v2) ────────────────────────────────────────────────
void OnDataRecvLegacy(const uint8_t *mac_addr, const uint8_t *incomingData, int len)
{
    memcpy(&incomingMessage, incomingData, sizeof(incomingMessage));

    Serial.println("==========================================");
    Serial.println("[RSU] ALERT RECEIVED");
    Serial.print  ("[RSU] Message: ");
    Serial.println(incomingMessage.text);
    Serial.println("==========================================");
}

// ─── Receive Callback (Core v3) ────────────────────────────────────────────────
#if defined(ESP_ARDUINO_VERSION) && ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
void OnDataRecv(const esp_now_recv_info *recv_info, const uint8_t *incomingData, int len)
{
    memcpy(&incomingMessage, incomingData, sizeof(incomingMessage));

    Serial.println("==========================================");
    Serial.println("[RSU] ALERT RECEIVED");
    Serial.print  ("[RSU] Message: ");
    Serial.println(incomingMessage.text);
    Serial.println("==========================================");
}
#endif

// ─── Setup ─────────────────────────────────────────────────────────────────────
void setup()
{
    Serial.begin(115200);

    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    Serial.println("==========================================");
    Serial.println(" AEGIS-RS RSU Receiver (ESP-NOW)");
    Serial.print(" Board MAC: ");
    Serial.println(WiFi.macAddress()); // Should print 00:4B:12:30:3D:3C
    Serial.println("==========================================");

    if (esp_now_init() != ESP_OK)
    {
        Serial.println("[RSU] ESP-NOW Init Failed");
        return;
    }

    // Register transmitter as peer
    esp_now_peer_info_t peerInfo;
    memset(&peerInfo, 0, sizeof(peerInfo));
    memcpy(peerInfo.peer_addr, transmitterMAC, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;

    if (esp_now_add_peer(&peerInfo) != ESP_OK)
        Serial.println("[RSU] Failed to add transmitter peer");
    else
        Serial.println("[RSU] Transmitter peer linked successfully");

    // Register receive callback
#if defined(ESP_ARDUINO_VERSION) && ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
    esp_now_register_recv_cb(OnDataRecv);
#else
    esp_now_register_recv_cb(OnDataRecvLegacy);
#endif

    Serial.println("[RSU] READY. Listening for alerts...");
}

// ─── Loop ──────────────────────────────────────────────────────────────────────
void loop()
{
    delay(100);
}
