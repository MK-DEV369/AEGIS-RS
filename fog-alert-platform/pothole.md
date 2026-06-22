

# 🚧 **End-to-End Pothole Detection & Alert System**

```plaintext
Camera → Frame Capture → YOLO Detection → Depth/Size Estimation
       → GPS Mapping → Risk Calculation → Backend → ESP32 Alert
```

---

# 🎥 **1. Frame Capture (Real-Time Input)**

### Source:

* Phone (IP Webcam)

```python
cap = cv2.VideoCapture(stream_url)
```

---

### Requirements:

* FPS: 10–20
* Resolution: 640×640 (YOLO optimal)

---

# 🧠 **2. Pothole Detection (YOLOv8)**

### Input:

[
I_t \in \mathbb{R}^{640 \times 640 \times 3}
]

---

### Output:

```json
{
  "class": "pothole",
  "bbox": [x, y, w, h],
  "confidence": 0.91
}
```

---

### Core math:

Bounding box:
[
B = (x, y, w, h)
]

Confidence:
[
Conf = P(object) \times IoU
]

---

# 📏 **3. Pothole Size Estimation (VERY IMPORTANT)**

You need **real-world dimensions**, not just pixels.

---

## 🔹 A. Pixel Area

[
A_{pixel} = w \times h
]

---

## 🔹 B. Approx Real Size (using scaling)

[
Size_{real} = \frac{A_{pixel}}{f}
]

Where:

* (f) = calibration factor (camera height + focal length)

---

## 🔹 C. Depth Approximation (simple)

Using vertical position:

[
Depth \propto \frac{1}{y}
]

👉 Lower in frame = closer

---

### Output:

```json
{
  "width": 0.5,
  "depth": 0.2,
  "distance": 8
}
```

---

# 📍 **4. Location Mapping (CRITICAL)**

You already have:

* ESP32 GPS
* OR phone GPS

---

### Combine:

```json
{
  "lat": 12.9716,
  "lng": 77.5946
}
```

---

### Sync with frame:

[
Location_t = GPS(t)
]

---

# 🧠 **5. Multi-Pothole Tracking**

If multiple detections:

```python
pothole_count = len(detections)
```

---

### Track across frames (optional):

* Use **SORT / DeepSORT**

---

# ⚠️ **6. Risk Calculation (Important)**

[
R = w_1(Size) + w_2(Depth) + w_3(Distance^{-1})
]

---

### Example:

```json
{
  "risk": 0.85,
  "severity": "HIGH"
}
```

---

# 📡 **7. Backend Transmission**

Send data:

```json
{
  "type": "pothole",
  "location": [lat, lng],
  "size": 0.5,
  "distance": 8,
  "risk": 0.85
}
```

---

# 📡 **8. ESP32 Communication (MQTT)**

### Topic:

```
aegis/pothole
```

---

### ESP32 receives:

```cpp
if (risk > 0.8) {
  buzzer_on();
  led_red();
}
```

---

# 🚗 **9. Vehicle Alert Logic (SMART PART)**

### If pothole is:

#### 🔴 Close (<10m)

* buzzer ON
* LED RED

#### 🟡 Medium (10–20m)

* LED YELLOW

#### 🟢 Far (>20m)

* no alert

---

### Formula:

[
Alert = f(Distance, Risk)
]

---

# 🔁 **10. Temporal Tracking (VERY IMPORTANT)**

Avoid duplicate alerts:

[
P_t = \alpha P_{new} + (1-\alpha)P_{prev}
]

---

### Or:

* store pothole ID
* ignore repeats

---

# 🗺 **11. Map Integration**

Send:

```json
{
  "lat": ...,
  "lng": ...,
  "severity": "HIGH"
}
```

---

### Display:

* red marker = dangerous pothole

---

# 🔥 **12. Full Real-Time Loop**

```plaintext
Frame →
Detect →
Estimate size →
Get GPS →
Compute risk →
Send →
ESP32 alert →
Dashboard update
```

---

# ⚡ **13. Optimization Tips (Important)**

### ✔ Use YOLOv8n (fast)

### ✔ Run detection every 2–3 frames

### ✔ Use batching if needed

---

# 🧠 **KEY INSIGHT (VERY IMPORTANT)**

👉 Detection alone is useless

You need:

**Detection + Location + Size + Risk + Communication**

---

# 🎯 **Final Output Example**

```json
{
  "type": "pothole",
  "location": [12.97, 77.59],
  "size": 0.6,
  "distance": 6,
  "risk": 0.9,
  "alert": "HIGH"
}
```

