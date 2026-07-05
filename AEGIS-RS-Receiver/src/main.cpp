#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>

// ─── Message Struct ────────────────────────────────────────────────────────────
// MUST match transmitter exactly (same struct, same size)
typedef struct struct_message {
    char text[250];
} struct_message;

struct_message incomingMessage;

// ─── Peer Config ───────────────────────────────────────────────────────────────
// Sender TX MAC Address: A0:B7:65:22:EB:14
uint8_t transmitterMAC[] = {0xA0, 0xB7, 0x65, 0x22, 0xEB, 0x14};

// ─── Internal handler ──────────────────────────────────────────────────────────
void handleAlert(const uint8_t *incomingData, int len)
{
    memcpy(&incomingMessage, incomingData, sizeof(incomingMessage));

    Serial.println("==========================================");
    Serial.println("[RSU] *** ALERT RECEIVED ***");
    Serial.print  ("[RSU] Payload: ");
    Serial.println(incomingMessage.text);
    Serial.println("==========================================");
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

// ─── Setup ─────────────────────────────────────────────────────────────────────
void setup()
{
    Serial.begin(115200);

    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    Serial.println("==========================================");
    Serial.println(" AEGIS-RS RSU Receiver (ESP-NOW)");
    Serial.print  (" Board MAC : ");
    Serial.println(WiFi.macAddress()); // Should print: 00:4B:12:30:3D:3C
    Serial.println("==========================================");

    // Init ESP-NOW
    if (esp_now_init() != ESP_OK)
    {
        Serial.println("[RSU] ERROR: ESP-NOW Init Failed");
        return;
    }

    // Register transmitter as known peer
    esp_now_peer_info_t peerInfo;
    memset(&peerInfo, 0, sizeof(peerInfo));
    memcpy(peerInfo.peer_addr, transmitterMAC, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;

    if (esp_now_add_peer(&peerInfo) != ESP_OK)
        Serial.println("[RSU] ERROR: Failed to add transmitter peer");
    else
        Serial.println("[RSU] Transmitter peer linked OK");

    // Register receive callback (Core version agnostic)
#if defined(ESP_ARDUINO_VERSION) && ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
    esp_now_register_recv_cb(OnDataRecv);
#else
    esp_now_register_recv_cb(OnDataRecvLegacy);
#endif

    Serial.println("[RSU] READY. Listening for ESP-NOW alerts...");
}

// ─── Loop ──────────────────────────────────────────────────────────────────────
void loop()
{
    // Receiver is fully callback-driven — nothing needed here
    delay(100);
}
