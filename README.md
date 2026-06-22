# 🛡️ AEGIS-RS: AI-Based Intelligent Multi-Hazard Road Monitoring System

AEGIS-RS (Active Engineering & Geolocation Intelligent System - Road Safety) is a comprehensive V2I2V (Vehicle-to-Infrastructure-to-Vehicle) road monitoring and ADAS (Advanced Driver Assistance Systems) platform. It integrates deep-learning models for real-time pothole/speed bump detection and fog prediction with wireless ESP-NOW transceiver modules.

---

## 📊 ML Model Performance & Results

### 1. Pothole Detection (YOLOv8 Nano)
Our custom-trained YOLOv8 Nano model (`yolov8n.pt`) segments and classifies road hazards across four severity levels: **CRITICAL**, **HIGH**, **MEDIUM**, and **LOW** based on proximity, depth estimation, and surface area calculations.

*   **Training Dataset Size**: roboflow annotations split (train/valid/test)
*   **Validation Performance (Final Epoch 30)**:
    
    | Metric | Value | Description |
    | :--- | :--- | :--- |
    | **mAP@50 (Box)** | **72.34%** | Mean Average Precision at 0.5 IoU threshold |
    | **mAP@50-95 (Box)** | **45.33%** | Mean Average Precision averaged over 0.5 to 0.95 IoU |
    | **Precision** | **63.72%** | True positive detection accuracy |
    | **Recall** | **71.64%** | Ability of model to find all potholes |
    | **Inference Latency** | **~150ms** | CPU inference time on laptop dev environment |

### 2. Fog Processing & Classification
The fog pipeline is split into a **Dehazing network** (FFA-Net) and a **Severity Classifier** (XGBoost head) to provide context-aware predictions.

#### A. FFA-Net Dehazing (Pre-processing)
Before running object detection or classification in foggy conditions, the image is passed through a Feature Fusion Attention Network (FFA-Net) to recover colors, edge clarity, and contrast.

*   **Validation Metrics**:
    *   **SSIM (Structural Similarity Index)**: **94.90%** (preserves structural fidelity post-dehazing)
    *   **PSNR (Peak Signal-to-Noise Ratio)**: **22.15 dB** (minimizes noise artifacts)
    *   **MSE (Mean Squared Error)**: **0.00657**

#### B. XGBoost Fog Severity Classifier
Features extracted from the dehazed frames (contrast, brightness, edge density, color attenuation) are classified using XGBoost into three levels: **LOW** (Clear), **MEDIUM** (Moderate Fog), and **HIGH** (Severe Fog).

*   **Classification Performance**:
    
    | Metric | Value | Description |
    | :--- | :--- | :--- |
    | **3-Class Accuracy** | **45.40%** | Baseline accuracy on 3-class tabular classification |
    | **Precision (Macro)** | **44.83%** | Averaged precision across classes |
    | **Recall (Macro)** | **44.13%** | Averaged recall across classes |
    | **F1-Score (Macro)** | **43.76%** | Balance of precision & recall |
    | **Inference Latency** | **7.63ms** | Tabular head classification speed |
    | **Throughput (System)** | **131.14 FPS** | Handcrafted feature extraction & classification rate |

---

## 📡 V2I2V Telemetry & ESP32 Integration

The platform relays active hazards to other connected vehicles or infrastructure elements over Serial and ESP-NOW broadcasts.

```
+------------------+         +---------------------+         +-----------------+
| Laptop Backend   |  Serial | Vehicle ESP         | ESP-NOW | RSU ESP         |
| (Django API      | ------->| (OBU Transmitter on | ------->| (Receiver on    |
|  & Python Relay) |         |  COM4 at 115200)    |         |  Roadside Unit) |
+------------------+         +---------------------+         +-----------------+
```

### 1. Pothole Deduplication Relay
*   The backend's spatial analysis tracking assigns persistent tracking IDs to potholes and increments the database `total_potholes` counter *only when a new unique pothole is detected*.
*   The serial relay daemon (`esp32_relay.py`) polls the API and alerts the Vehicle ESP32 **only when a new unique pothole is detected** (when `total_potholes` increments), preventing duplicate alerts for the same pothole on consecutive frames.

### 2. Fog Warnings
*   If the fog level rises to warning thresholds (`MEDIUM`, `HIGH`, `CRITICAL`), the relay daemon constructs and writes a `FOG:` packet over serial to the Vehicle ESP32.
*   Once the system returns to clear conditions, a clear command (`FOG:NONE`) is sent to reset alerts.

### 3. Road Side Unit (RSU) Output Formats
When the RSU receiver captures the broadcasted packets, it writes the telemetry to its serial port in the following JSON-compliant structure:

*   **Pothole Warning**:
    ```json
    {"type":"RSU_Pothole","lat":12.924285,"lng":77.499673,"vehicle_id":"OBU-01","speed":35,"status":"DISSEMINATED"};
    ```
*   **Fog Warning**:
    ```json
    {"type":"RSU_Fog","lat":12.924285,"lng":77.499673,"vehicle_id":"OBU-01","speed":35,"status":"DISSEMINATED"};
    ```

---

## 📡 Interactive V2I Simulation Loop

AEGIS-RS supports an end-to-end V2I (Vehicle-to-Infrastructure) simulation loop when both the Vehicle OBU ESP32 and the Road Side Unit (RSU) ESP32 are connected to the laptop. 

```
[Frontend Map UI] --(POST Simulate API)--> [Django Backend]
                                                    |
[Interactive Map] <--(Poll Telemetry Latest)-- [Python Relay] --(Serial POTHOLE/FOG)--> [Vehicle OBU ESP32]
                                      ^             |                                        |
                                      |             | (Serial Ingest)                    (ESP-NOW)
                                      |             v                                        v
                               [Django Telemetry] <---+------------------------------ [RSU ESP32 Receiver]
```

### 1. Manual Simulation Endpoints
We provide manual API routes to simulate OBU hazard detections at specific GPS locations without requiring camera feeds:
*   **Pothole Sim**: `POST /api/simulate/pothole/` (Payload: `lat`, `lng`, `severity`, `source_id`)
*   **Fog Sim**: `POST /api/simulate/fog/` (Payload: `lat`, `lng`, `fog_level`, `risk_score`, `source_id`)

### 2. Closed-Loop Ingestion Flow
1.  **Trigger Event**: In the frontend Live Map, enter coordinates (defaults to Kengeri test area `12.9242853, 77.4996733`) and trigger an alert.
2.  **Relay transmission**: The python relay daemon detects the new database record and sends the command over serial to the **Vehicle ESP32 (Transmitter)**.
3.  **Wireless Broadcast**: The Vehicle ESP32 broadcasts it over ESP-NOW.
4.  **RSU Reception**: The **RSU ESP32 (Receiver)** receives the broadcast and outputs the disseminated JSON log:
    `{"type":"RSU_Pothole","lat":12.924285,"lng":77.499673,"vehicle_id":"OBU-01","speed":35,"status":"DISSEMINATED"};`
5.  **Relay Ingest**: The relay daemon intercepts this JSON on the RSU's serial port, parses it, and forwards it to the backend `/api/telemetry/ingest/` endpoint.
6.  **Dynamic Rendering**: The frontend Leaflet map page pulls the latest telemetry and draws a violet/blue double-ringed warning marker representing a successfully disseminated V2I hazard alert!

---

## 🚀 Startup & Launching

To run the full stack (React frontend, Django backend, and ESP32 relay daemon):
1.  Double-click [start_all.bat](file:///e:/6th%20SEM%20Data/Projects/AEGIS-RS_IDP/start_all.bat) at the workspace root.
2.  The script will automatically check directory paths, activate the virtual environment, and spin up three separate CMD consoles to run:
    *   **Django Server**: `http://127.0.0.1:8000`
    *   **React Frontend (Vite)**: `http://localhost:5173`
    *   **ESP32 Relay Daemon**: Automatically connects to all active serial COM ports (e.g. COM4 and COM5).
3.  Navigate to `/live-map` in the browser, trigger simulated alerts from the sidebar panel, and watch the warnings populate in real-time.
