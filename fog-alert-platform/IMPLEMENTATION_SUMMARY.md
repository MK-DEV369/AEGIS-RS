# Real-Time Detection Debugging - Implementation Summary

## What Was Added

### 1. Enhanced Debug Logging in `services.py`
- **YOLO Detector** (`_predict_results` method):
  - Added detailed model path logging
  - Added model load status checks
  - Logs selected model path and why it was chosen
  - Reports exact error if model fails to load

- **Pothole Detection** (`predict_pothole_only_from_bytes` method):
  - Added YOLO detection status validation
  - Added frame annotation validation checks
  - Added cv2.imencode error catching with exception details
  - Logs frame bytes size before and after encoding
  - Validates frame dimensions and data

### 2. Enhanced Health Check Endpoint (`/api/health/`)
Returns comprehensive model validation status:
```json
{
  "validation": {
    "yolo": {
      "selected_path": "...",
      "path_exists": true/false,
      "is_loaded": true/false,
      "load_error": "error message or null",
      "status": "✓ Ready or ✗ Error"
    },
    "dehazer": { ... },
    "xgboost": { ... }
  }
}
```

Access: `curl http://127.0.0.1:8000/api/health/ | jq .validation`

### 3. Validation Pipeline Script (`scripts/validate_pipeline.py`)
Complete end-to-end validation that:
- Checks YOLO model loads successfully
- Validates dehazer model configuration
- Verifies XGBoost fog model
- Tests pothole detection on sample frame
- Tests fog detection on sample frame
- Produces clear pass/fail report

**Usage**:
```bash
cd fog-alert-platform/backend
python scripts/validate_pipeline.py
```

### 4. Stream Diagnostics Script (`scripts/diagnose_streams.py`)
Real-time monitoring tool that:
- Shows model status
- Lists active camera sources
- Displays latest pothole/fog detections
- Checks if annotated frames are being cached
- Tests MJPEG stream endpoints
- Can run continuously with `--loop N`

**Usage**:
```bash
python scripts/diagnose_streams.py \
  --backend-url http://127.0.0.1:8000 \
  --pothole-source phone_pothole_01 \
  --fog-source phone_fog_01 \
  --loop 5  # Refresh every 5 seconds
```

### 5. Comprehensive Documentation

#### `DEBUGGING_GUIDE.md` - Complete Reference
Includes:
- Problem summary and root causes
- Step-by-step diagnosis workflow
- Common issues and solutions
- Logging setup instructions
- Manual test procedures
- Performance checklist

#### `QUICK_FIX_CHECKLIST.md` - Fast Troubleshooting
Includes:
- 30-second diagnosis
- Issue-specific fixes (6 common problems)
- Copy-paste commands
- Real-time monitoring setup
- When-everything-passes troubleshooting

---

## Quick Start: Finding Your Issue

### Step 1: Run Validation
```bash
cd fog-alert-platform/backend
python scripts/validate_pipeline.py
```

**Results:**
- ✓ All pass → Go to Step 2
- ✗ YOLO fails → See `QUICK_FIX_CHECKLIST.md` Issue 1
- ✗ Dehazer fails → See Issue 2
- ✗ XGBoost fails → See Issue 3
- ✗ Detection test fails → See Issue 4

### Step 2: Monitor Live Streams
```bash
python scripts/diagnose_streams.py --loop 3
```

**Look for:**
- All models showing "Ready"
- Recent requests in sources status
- Pothole/Fog frames with recent timestamps
- MJPEG streams responding

**Issues:**
- No recent frames → Camera not sending data
- Frames exist but no box → Go to Step 3
- Errors in status → See DEBUGGING_GUIDE.md

### Step 3: Check Latest Frame
```bash
# Get latest pothole frame
curl -s http://127.0.0.1:8000/api/pothole/latest-frame/ -o frame.jpg && file frame.jpg

# Get latest fog frame
curl -s http://127.0.0.1:8000/api/fog/latest-frame/ -o fog.jpg && file fog.jpg
```

**Expected**: "JPEG image data" with size > 1000 bytes
**Problem**: 404 or very small file → Frame not cached

### Step 4: Check Frontend
In browser console:
```javascript
// Check source IDs
console.log('Sources:', {pothole: potholeSourceId, fog: fogSourceId});

// Test API directly
fetch('/api/pothole/latest-frame/?source_id=phone_pothole_01')
  .then(r => console.log('Status:', r.status, 'Size:', r.headers.get('content-length')));
```

---

## Integration Points

### Modified Files
1. **`fog_api/services.py`** (Lines 311-315, 1097-1116):
   - Enhanced YOLO loader error logging
   - Added frame annotation validation
   - Added encoding error handling

2. **`fog_api/views.py`** (Lines 1-7, 81-132):
   - Added Path import
   - Enhanced HealthView with model validation

### New Files
1. `scripts/validate_pipeline.py` - Validation suite
2. `scripts/diagnose_streams.py` - Diagnostics tool
3. `DEBUGGING_GUIDE.md` - Reference documentation
4. `QUICK_FIX_CHECKLIST.md` - Fast troubleshooting

---

## Configuration for Better Debugging

### Enable Debug Logging
Edit `config/settings.py`:
```python
# Enable pipeline debug logs
PIPELINE_DEBUG_LOGS = True

# Optional: Log to file
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(asctime)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log'),
        logging.StreamHandler()
    ]
)
```

### Check Settings
```python
# Critical settings to verify
YOLOV8_MODEL_PATH = "models/yolov8n.pt"  # Must exist
DEHAZE_ENABLED = True  # Set to False to skip dehazing
REALTIME_SKIP_DEHAZE = False  # For testing
REALTIME_MAX_FRAME_SIDE = 480  # For resizing

# Frame caching
SOURCE_STATUS_TTL_SECONDS = 300  # 5 minutes
STREAM_CHUNK_TTL_SECONDS = 600  # 10 minutes

# Frontend
FRONTEND_STREAM_FPS = 3.0  # MJPEG stream FPS
```

---

## What the Logs Will Show

### Successful Detection Flow
```
[DEBUG] predict_pothole_only_from_bytes START: source_id=phone_pothole_01
[DEBUG] Image decoded: shape=(480, 640, 3), dtype=uint8
[DEBUG] Frame prepared: realtime_meta={'realtime': True}
[DEBUG] Dehazing complete: method=ffa_rtts_annotation_model
[DEBUG] YOLO detection complete: count=2
[DEBUG] Analysis complete: max_risk=0.75
[DEBUG] Frame enhanced: enhanced_annotated_bgr_available=True
[DEBUG] Annotated frame encoded: size_bytes=45231
[DEBUG] Database record created: record_id=42
[DEBUG] predict_pothole_only_from_bytes COMPLETE
```

### When Something Fails
```
[ERROR] YOLO model failed to load: model not found at path
[ERROR] cv2.imencode returned False - encoding failed
[ERROR] enhanced_annotated_bgr is None after _enhance_pothole_frame
```

---

## Performance Tips

1. **Use Real-Time Mode**: Ensures lower latency
   ```python
   realtime=True  # In requests
   ```

2. **Adjust YOLO Size**: Smaller = faster but less accurate
   ```python
   YOLOV8_IMGSZ_REALTIME = 416  # Default 640
   ```

3. **Skip Dehazing if Not Needed**:
   ```python
   REALTIME_SKIP_DEHAZE = True
   ```

4. **Monitor Memory**: Models can use 500MB+ RAM
   ```bash
   watch -n 1 'ps aux | grep python | grep manage'
   ```

---

## Testing Workflow

### Quick Test
```bash
# 1. Run validation
python scripts/validate_pipeline.py

# 2. Monitor streams
python scripts/diagnose_streams.py --loop 2 &

# 3. Send test frame
curl -X POST http://127.0.0.1:8000/api/pothole/predict/ \
  -F "image=@test_image.jpg" \
  -F "source_id=phone_pothole_01" \
  -F "realtime=true"

# 4. Check if frame cached
curl -s http://127.0.0.1:8000/api/pothole/latest-frame/ \
  -o latest.jpg && file latest.jpg
```

### Full Integration Test
1. Start backend server
2. Run `diagnose_streams.py --loop 5`
3. Start frontend React app
4. Start camera stream relay:
   ```bash
   python scripts/phone_stream_relay.py \
     --phone-base-url http://<PHONE_IP>:6969 \
     --mode pothole \
     --realtime
   ```
5. Open frontend and verify streaming + annotations

---

## Next Steps

1. **Run validation script** to identify blockers
2. **Consult QUICK_FIX_CHECKLIST** for your specific issue
3. **Enable debug logging** and monitor `diagnose_streams.py`
4. **Read DEBUGGING_GUIDE** for detailed solutions
5. **Test with manual API calls** to isolate issues

