# Fog-Alert-Platform Real-Time Annotation Debugging Guide

## Problem Summary

**Symptom**: Both cameras are livestreaming, but annotated boxes (bounding boxes with pothole/fog labels) are not shown in real-time on the frontend.

**Root Cause**: The issue is typically in one of these places:
1. **YOLO model not loaded** - The pothole detection model fails to initialize
2. **Annotated frames not being generated** - Detection runs but frame annotation fails
3. **Frame bytes not being cached** - Frames are generated but not stored in runtime state
4. **MJPEG stream not fetching latest frames** - Frames are cached but not served correctly

---

## Quick Diagnosis Steps

### Step 1: Check Model Status
Run the validation script to ensure all models are properly loaded:

```bash
cd fog-alert-platform/backend
python scripts/validate_pipeline.py
```

**What to look for:**
- `YOLO Model` should show `✓ Ready` 
- `Dehazer Model` should show `✓ Ready`
- `XGBoost Model` should show `✓ Ready`
- `Pothole Detection` and `Fog Detection` should show `✓ PASS`

### Step 2: Check Live Stream Status
Monitor what's happening with active streams:

```bash
python scripts/diagnose_streams.py \
  --backend-url http://127.0.0.1:8000 \
  --pothole-source phone_pothole_01 \
  --fog-source phone_fog_01 \
  --loop 5  # Refresh every 5 seconds
```

**What to look for:**
- Model validation should show all components loaded
- Sources status should show recent requests
- Pothole/Fog frames should have recent timestamps
- MJPEG streams should be responding

### Step 3: Check Backend Logs
Enable debug logging and watch the Django output:

```bash
# In your Django settings, ensure:
PIPELINE_DEBUG_LOGS = True
DEBUG = True
LOGGING['loggers']['fog_api']['level'] = 'DEBUG'
```

Then in backend terminal, look for:
```
[DEBUG] predict_pothole_only_from_bytes START
[DEBUG] YOLO detection complete: count=...
[DEBUG] Frame enhanced: enhanced_annotated_bgr_available=True
[DEBUG] Annotated frame encoded: size_bytes=...
[DEBUG] Database record created: record_id=...
```

---

## Common Issues & Solutions

### Issue 1: YOLO Model Not Loading
**Symptom**: `YOLO Model: ✗ FAIL` or `is_loaded: False`

**Diagnosis output**:
```
[DEBUG] YOLO resolved model path: /path/to/model.pt
[DEBUG] YOLOv8 model file not found at /path/to/model.pt
```

**Solutions**:
1. **Check model path exists**:
   ```bash
   ls -la fog-alert-platform/backend/models/yolov8*.pt
   ```

2. **Check settings.py for correct path**:
   ```python
   YOLOV8_MODEL_PATH = "path/to/your/model.pt"
   ```

3. **Download the model if missing**:
   ```bash
   cd fog-alert-platform/backend/models
   # Download your YOLO model here
   ```

---

### Issue 2: Annotated Frames Not Generated
**Symptom**: `Pothole Detection: ✗ FAIL` with message about `_annotated_frame_bytes`

**Debug logs to check**:
```
[DEBUG] YOLO detection complete: count=0  # No detections
[DEBUG] Frame enhanced: enhanced_annotated_bgr_available=False  # Frame enhancement failed
[DEBUG] cv2.imencode returned False  # JPEG encoding failed
```

**Solutions**:
1. **Ensure dehazing is not broken**:
   - Check REALTIME_SKIP_DEHAZE setting
   - Verify dehazer model loads (Issue 1 above)

2. **Check frame dimensions**:
   - YOLO requires specific input sizes
   - Check `YOLOV8_IMGSZ` setting (usually 640)
   - Check `REALTIME_MAX_FRAME_SIDE` setting (usually 480)

3. **Check JPEG encoding**:
   ```bash
   # Test encoding manually
   python -c "
   import cv2
   import numpy as np
   frame = np.zeros((480, 640, 3), dtype=np.uint8)
   ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
   print(f'JPEG encoding: {ok}')
   "
   ```

---

### Issue 3: Frames Not Being Cached in Runtime State
**Symptom**: Frames processed but `/api/pothole/latest-frame/` returns 404

**Debug logs**:
```
[DEBUG] Annotated frame encoded: size_bytes=12345
[DEBUG] runtime_state.update_pothole_detection source=... frame_bytes_len=12345
```
But latest-frame API still returns 404.

**Solutions**:
1. **Check runtime_state is receiving frames**:
   ```bash
   python manage.py shell
   from fog_api.runtime_state import runtime_state
   frames = runtime_state.list_pothole_detections(limit=5)
   print(len(frames), "recent detections")
   for f in frames:
       print(f"  {f.get('source_id')}: frame_count={f.get('frame_count')}")
   ```

2. **Check source_id matches**:
   - Frontend requests `phone_pothole_01`
   - Backend receiving `phone_pothole_01` (should match exactly)
   - Check header of live monitoring page

3. **Check TTL settings** (frames expire after this time):
   ```python
   SOURCE_STATUS_TTL_SECONDS = 300  # 5 minutes
   ```

---

### Issue 4: MJPEG Stream Not Showing Latest Frames
**Symptom**: Stream responds but shows placeholder instead of actual frames

**Debug steps**:
1. **Check if stream endpoint is responding**:
   ```bash
   curl -I http://127.0.0.1:8000/api/pothole/stream/?source_id=phone_pothole_01
   # Should return 200 with multipart/x-mixed-replace content type
   ```

2. **Check if latest frame is actually being fetched**:
   ```bash
   # Get one frame from MJPEG stream
   curl -N http://127.0.0.1:8000/api/pothole/stream/?source_id=phone_pothole_01 \
     --max-time 2 -o test_frame.jpg
   
   # Check if it's a real frame or placeholder
   file test_frame.jpg
   ```

3. **Check FPS setting**:
   ```python
   FRONTEND_STREAM_FPS = 3.0  # Frames per second in stream
   ```

---

## Detailed Debugging Workflow

### Enable Comprehensive Logging

**1. Update settings.py**:
```python
PIPELINE_DEBUG_LOGS = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/pipeline_debug.log',
            'formatter': 'verbose',
        },
    },
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'loggers': {
        'fog_api': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
        },
    },
}
```

**2. Restart backend** and send a test frame

**3. Check logs**:
```bash
tail -f logs/pipeline_debug.log | grep "\[DEBUG\]"
```

### Send Test Frame Manually

```bash
# Using curl to send a test image
curl -X POST http://127.0.0.1:8000/api/pothole/predict/ \
  -F "image=@test_image.jpg" \
  -F "source_id=test_source" \
  -F "realtime=true" \
  -H "Accept: application/json" | jq .
```

**Expected response** should include:
```json
{
  "request_id": "...",
  "pothole_summary": {
    "pothole_count": 0,
    "detections_analyzed": 0,
    ...
  },
  "detections": { "items": [...] },
  "pipeline": { "real_time_ready": true },
  ...
}
```

---

## Health Check Endpoint

The enhanced `/api/health/` endpoint now shows:

```bash
curl http://127.0.0.1:8000/api/health/ | jq .validation
```

Example output:
```json
{
  "validation": {
    "yolo": {
      "selected_path": "/path/to/model.pt",
      "path_exists": true,
      "is_loaded": true,
      "load_error": null,
      "status": "✓ Ready"
    },
    "dehazer": {
      "enabled": true,
      "is_loaded": true,
      "load_error": null,
      "status": "✓ Ready"
    },
    "xgboost": {
      "model_path": "/path/to/fog_model.pkl",
      "path_exists": true,
      "is_loaded": true,
      "status": "✓ Ready"
    }
  }
}
```

---

## Performance Checklist

- [ ] All models loaded successfully
- [ ] YOLO detections return non-zero count on valid frames
- [ ] Annotated frames being generated and encoded
- [ ] Frame bytes stored in runtime_state
- [ ] `/api/pothole/latest-frame/` returns 200 status
- [ ] `/api/pothole/stream/` MJPEG stream has valid image data
- [ ] Frontend fetches correct source_id
- [ ] Inference latency < 1000ms for real-time mode
- [ ] No memory leaks (check `ps aux | grep python`)

---

## Additional Resources

- **Model files location**: `fog-alert-platform/backend/models/`
- **Settings file**: `fog-alert-platform/backend/config/settings.py`
- **Main service code**: `fog-alert-platform/backend/fog_api/services.py:810-1184`
- **Validation scripts**: `fog-alert-platform/backend/scripts/validate_pipeline.py`
- **Diagnostics scripts**: `fog-alert-platform/backend/scripts/diagnose_streams.py`

