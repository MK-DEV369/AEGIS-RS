

# 🌫 **End-to-End Fog Prediction Pipeline (Camera-Based)**

```plaintext
Camera → Frame Capture → Preprocessing → Dehazing → Feature Extraction
      → Fog Estimation → Temporal Smoothing → Risk Integration
      → Dashboard + Alerts
```

---

# 🎥 **1. Frame Capture (Input Layer)**

### Source:

* Phone (IP Webcam / RTSP)

### Key idea:

Fog is **temporal**, so capture continuous frames:

```python
cap = cv2.VideoCapture(stream_url)
```

---

### Important:

* Capture at **10–20 FPS**
* Use timestamps:
  [
  t = \text{current frame time}
  ]

---

# 🧼 **2. Preprocessing**

### Steps:

* Resize (e.g., 640×640)
* Normalize
* Convert color space (RGB → HSV optional)

---

### Why:

* Standardizes input for models
* Improves consistency

---

# 🌫 **3. Dehazing (Critical Step)** FFA-Net

### Input:

[
I(x)
]

### Output:

[
J(x)
]

Using:
[
J(x) = \frac{I(x) - A}{t(x)} + A
]

---

### Why dehazing first?

Fog causes:

* low contrast
* blurred edges

👉 Without dehazing:

* YOLO misses objects
* features become unreliable

---

### Your implementation:

* FFA-Net 

---

# 🧠 **4. Feature Extraction (Core Intelligence)**

Extract **fog-relevant features** from image

---

## 🔹 A. Contrast

[
C = \frac{I_{max} - I_{min}}{I_{max} + I_{min}}
]

👉 Fog ↓ contrast

---

## 🔹 B. Brightness

[
B = \frac{1}{N} \sum I(x)
]

👉 Fog ↑ brightness (scattering)

---

## 🔹 C. Edge Density

```python
edges = cv2.Canny(img, 100, 200)
edge_density = np.sum(edges) / img.size
```

👉 Fog ↓ edges

---

## 🔹 D. Color Attenuation

[
Depth \propto (V - S)
]

👉 Fog affects color saturation

---

# 🤖 **5. Fog Prediction Model (XGBoost)**

Input:

```plaintext
[contrast, brightness, edge_density, color_diff]
```

---

### Prediction:

[
P(fog) = f(x)
]

Output:

```json
{
  "fog_level": "HIGH",
  "probability": 0.82
}
```

---

# 🧠 **6. YOLO Integration (Context Awareness)**

Run detection in parallel:

```plaintext
YOLO → detects vehicles / road
```

---

### Why needed:

* Fog affects object visibility
* Combine:

  * object count
  * object clarity

---

# 🔁 **7. Temporal Smoothing (VERY IMPORTANT)**

Fog is not frame-by-frame—it evolves.

---

### Use moving average:

[
F_t = \alpha f_t + (1 - \alpha) F_{t-1}
]

---

### Why:

* Reduces noise
* Prevents flickering predictions

---

# 👁 **8. Visibility Estimation**

From contrast:

[
Visibility \propto \frac{1}{C}
]

---

Example:

```json
{
  "visibility": 35
}
```

---

# ⚠️ **9. Fog Classification Levels**

Convert probability → category:

```python
if p > 0.7:
    fog = "HIGH"
elif p > 0.4:
    fog = "MEDIUM"
else:
    fog = "LOW"
```

---

# 🚨 **10. Risk Integration**

Final step:

[
R = w_1 F + w_2 H + w_3 T + w_4 V^{-1}
]

---

Where:

* (F): fog score
* (H): hazards
* (T): traffic
* (V): visibility

---

# 📡 **11. Output Pipeline**

```plaintext
Fog Model → Backend API → Dashboard + ESP32
```

---

Example:

```json
{
  "fog": "HIGH",
  "visibility": 30,
  "risk": 0.85,
  "recommendation": "Reduce speed"
}
```

---

# 🎨 **12. Visualization (Frontend)**

Show:

* Fog level
* Visibility meter
* Heatmap

---

# 🔥 **KEY INSIGHT (Very Important)**

👉 Fog prediction is NOT:

> “CNN says fog or no fog”

👉 It is:

> **physics + vision + ML + temporal reasoning**

---

# 🎯 **Final System Summary**

```plaintext
Camera
 ↓
Dehazing (FFA-Net)
 ↓
Feature Extraction
 ↓
XGBoost Fog Prediction
 ↓
Temporal Smoothing
 ↓
Visibility Estimation
 ↓
Risk Engine
 ↓
Alerts + Dashboard
```

