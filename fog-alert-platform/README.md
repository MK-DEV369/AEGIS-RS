# 🌫️ Fog Alert Platform (AEGIS-RS Dashboard & Services)

A modern full-stack intelligent road hazard monitoring system and ADAS (Advanced Driver Assistance Systems) telemetry dashboard. This platform combines a high-performance **Django REST API** backend running deep-learning inference pipelines with a polished **React TypeScript** frontend for live monitoring, interactive mapping, and alerts.

---

## 📁 Repository Structure

```
fog-alert-platform/
├── backend/                  # Django REST API & ML Inference Engines
│   ├── config/               # Settings, routing, and environment vars
│   ├── fog_api/              # Models, views, serializers, and core services
│   ├── scripts/              # Serial relay, ADB forwarder, and telemetry senders
│   └── venv/                 # Python virtual environment
│
├── frontend/                 # React TypeScript Vite SPA
│   ├── public/               # Static icons, overlays, and styles
│   ├── src/                  # Components, interactive Leaflet maps, and pages
│   │   ├── components/       # UI visual enhancement assets (WebGL waves, border glows)
│   │   └── pages/            # Homepage, Dashboard, Monitoring, Map, and Alerts
│   └── vite.config.ts        # Vite configuration & backend proxy routing
│
└── README.md                 # This file (Platform Overview & Integration)
```

---

## 🚀 System Architecture & Integrations

The system is designed for active road hazard monitoring by capturing real-time camera frames (via mobile phones or IP cameras), performing inference, and propagating telemetry down to in-vehicle transceivers.

```
+------------+       +-------------------+       +------------------+       +---------------+
| IP Webcam  | JPEG  | Django Backend    | Serial| Vehicle ESP32    |ESP-NOW| RSU ESP32     |
| Phone/Cam  |------>| (Inference &      |------>| (Transmitter on  |------>| (Receiver on  |
| (Source)   |       |  Deduplication)   |       |  COM4 at 115200) |       |  Roadside)    |
+------------+       +-------------------+       +------------------+       +---------------+
                               |
                               | REST API
                               v
                     +-------------------+
                     | React Dashboard   |
                     | (Vite App UI)     |
                     +-------------------+
```

---

## 📊 Evaluation & Machine Learning Results

### 1. Pothole & Speed Bump Detection (YOLOv8 Nano)
We custom-trained YOLOv8 Nano (`yolov8n.pt`) to detect potholes and evaluate their severity (CRITICAL, HIGH, MEDIUM, LOW) based on proximity, depth estimation, and surface area calculations.

*   **Dataset Source**: Roboflow road anomaly segmentations
*   **Validation Metrics (Final Epoch 30)**:
    
    | Metric | Score | Description |
    | :--- | :--- | :--- |
    | **mAP@50 (Box)** | **72.34%** | Mean Average Precision at 0.5 IoU threshold |
    | **mAP@50-95 (Box)** | **45.33%** | Mean Average Precision averaged over 0.5 to 0.95 IoU |
    | **Precision** | **63.72%** | Bounding box positive classification rate |
    | **Recall** | **71.64%** | Percentage of actual potholes successfully located |
    | **Latency** | **~150ms** | CPU inference time per frame |

### 2. Fog Pre-processing & Tabular Classification

#### A. FFA-Net Dehazing Network
Before running classification or object detection in low-visibility environments, frames pass through a Feature Fusion Attention Network (FFA-Net) to remove fog, restore edges, and improve contrast.

*   **Validation Performance**:
    *   **SSIM (Structural Similarity Index)**: **94.90%** (preserves structural fidelity post-dehazing)
    *   **PSNR (Peak Signal-to-Noise Ratio)**: **22.15 dB** (minimizes noise artifacts)
    *   **MSE (Mean Squared Error)**: **0.00657**

#### B. XGBoost Fog Severity Classifier
Handcrafted visual features (contrast, brightness, color attenuation, and edge density) are extracted from the dehazed frame and evaluated by an XGBoost model.

*   **3-Class Severity Classification (LOW, MEDIUM, HIGH)**:
    
    | Metric | Score | Description |
    | :--- | :--- | :--- |
    | **3-Class Accuracy** | **45.40%** | Multi-class classification accuracy |
    | **Precision (Macro)** | **44.83%** | Average precision across classes |
    | **Recall (Macro)** | **44.13%** | Average recall across classes |
    | **F1-Score (Macro)** | **43.76%** | Balance of precision & recall |
    | **Inference Latency** | **7.63ms** | Tabular classifier execution time |
    | **System Throughput** | **131.14 FPS** | Handcrafted feature extraction & classification rate |

---

## 📡 Hardware & V2I2V Serial Protocol

When a pothole or fog hazard is identified, the backend routes the details to connected transceivers.

### 1. Spatial Deduplication
The backend tracks potholes across frames by centroid similarity. It only increments the `total_potholes` counter for *new unique* potholes. The python relay daemon (`backend/scripts/esp32_relay.py`) polls the API and alerts the Vehicle ESP32 over serial **only when a new unique pothole is detected**, preventing duplicate serial alerts for the same pothole on consecutive frames.

### 2. Protocol Serial Syntax
*   **Pothole Alert**: `POTHOLE:<severity>,<lat>,<lng>,<count>,<source_id>\n`
*   **Fog Alert**: `FOG:<fog_level>,<lat>,<lng>,<risk_score>,<source_id>\n`
*   **Fog Clear**: `FOG:NONE,<lat>,<lng>,0,<source_id>\n`

### 3. Road Side Unit (RSU) Output Logs
When roadside receivers detect the ESP-NOW broadcasts, they log formatted JSON metrics to their debug consoles for easy ingestion by local nodes:
*   **Pothole**: `{"type":"RSU_Pothole","lat":12.924285,"lng":77.499673,"vehicle_id":"OBU-01","speed":35,"status":"DISSEMINATED"};`
*   **Fog**: `{"type":"RSU_Fog","lat":12.924285,"lng":77.499673,"vehicle_id":"OBU-01","speed":35,"status":"DISSEMINATED"};`

---

## ⚙️ How to Run locally

### Quick-Start Orchestrator
You can run the entire platform concurrently by executing the batch script at the workspace root:
```powershell
# In the repository root:
.\start_all.bat
```
This launches separate console windows for the backend server, frontend Vite dev server, and serial relay daemon.

---

### Manual Launching Instructions

#### 1. Backend Server Setup
Ensure Python 3.11 is installed, navigate to `backend/`, and activate the environment:
```powershell
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```
API endpoints will load at `http://127.0.0.1:8000/`.

#### 2. Frontend Dashboard Setup
Make sure Node.js (v18+) is installed, navigate to `frontend/`, and run Vite:
```powershell
cd frontend
npm install
npm run dev
```
The React monitoring panel will launch at `http://localhost:5173/`.

#### 3. ESP32 Serial Relay
With both the Vehicle OBU and RSU ESP32 devices connected to your laptop:
```powershell
# Activate backend venv first:
cd backend
python -u scripts/esp32_relay.py
```
This automatically binds to all active USB serial COM ports (e.g. `COM4` and `COM5`) at baud rate `115200`. It will relay outbound telemetry to the transmitter, and automatically listen for inbound JSON logs from the receiver to post them back to the backend telemetry database.

---

## 📡 Interactive V2I2V Simulation Cycle

The platform supports a closed-loop manual simulator to test your transceivers without camera feeds:

1.  **Frontend trigger**: Open `/live-map` and trigger a simulated warning from the **OBU V2X Simulator** panel.
2.  **Relay transmission**: The python relay detects the new status on the Django API and writes a serial stream (e.g. `POTHOLE:MEDIUM,12.924285,77.499673,1,OBU-01`) to the transmitter OBU.
3.  **ESP-NOW Broadcast**: The transmitter OBU broadcasts the packed binary struct wirelessly.
4.  **RSU Capture**: The roadside RSU receiver receives the packet and logs the formatted string to its serial port:
    `{"type":"RSU_Pothole","lat":12.924285,"lng":77.499673,"vehicle_id":"OBU-01","speed":35,"status":"DISSEMINATED"};`
5.  **Relay Ingest**: The relay daemon intercepts this JSON on the RSU serial port, parses it, and POSTs it back to `/api/telemetry/ingest/`.
6.  **Real-Time Mapping**: The map component polls `/api/telemetry/latest/` and displays a dashed violet/blue double-ringed warning marker showing successful wireless delivery.

