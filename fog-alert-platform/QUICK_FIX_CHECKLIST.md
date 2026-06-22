# QUICK TROUBLESHOOTING CHECKLIST

## 30-Second Diagnosis

Run this first:
```bash
cd fog-alert-platform/backend
python scripts/validate_pipeline.py
```

If you see **✓ ALL CHECKS PASSED**, skip to "Live Stream Issue". Otherwise, identify which failed:

---

## Issue 1: YOLO Model Not Loading ❌
**Signs**: Model load fails in validation script

### Fix:
1. Check file exists:
   ```bash
   ls -la models/yolov8*.pt
   ```

2. Fix path in `config/settings.py`:
   ```python
   YOLOV8_MODEL_PATH = "models/yolov8n.pt"  # Full path from backend dir
   ```

3. Restart Django server

4. Re-run validation script

---

## Issue 2: Dehazer Model Not Loading ❌
**Signs**: "Dehazer not loaded" in validation

### Fix:
1. Check path in `config/settings.py`:
   ```python
   DEHAZE_MODEL_PATH = "models/ffa_dehaze.pt"  # Check this exists
   DEHAZE_ENABLED = True  # Or set to False to skip dehazing
   ```

2. If file missing:
   ```bash
   # Either download model or set to False
   DEHAZE_ENABLED = False
   ```

3. Restart server and test again

---

## Issue 3: XGBoost Model Not Loading ❌
**Signs**: "XGBoost not loaded" in validation, fog detection fails

### Fix:
1. Check fog model exists:
   ```bash
   ls -la models/xgboost*.pkl
   ls -la RTTS/xgboost_fog/  # Check for features.py
   ```

2. Verify settings:
   ```python
   XGBOOST_FOG_MODEL_PATH = "models/xgboost_fog_model.pkl"
   XGBOOST_FOG_DIR = "RTTS/xgboost_fog"
   ```

3. Ensure feature extraction script exists

---

## Issue 4: Detection Works But No Annotated Frames ❌
**Signs**: Models load, test detection runs, but no frame bytes in response

### Check Detection Output:
```bash
cd fog-alert-platform/backend
python manage.py shell
from fog_api.services import fog_predictor
from PIL import Image
import io

# Create test image
test_img = Image.new('RGB', (640, 480), color='blue')
img_bytes = io.BytesIO()
test_img.save(img_bytes, format='JPEG')
img_bytes = img_bytes.getvalue()

# Test pothole detection
result = fog_predictor.predict_pothole_only_from_bytes(img_bytes, source_id='test')
print("Has annotated frame:", "_annotated_frame_bytes" in result)
print("Detections:", result.get('detections', {}).get('count'))
```

### If NO annotated frame:
1. Check if YOLO detections are working:
   ```python
   print(result.get('detections', {}).get('count'))
   # Should be >= 0
   ```

2. Check frame enhancement:
   ```bash
   tail -f logs/*.log | grep "Frame enhanced"
   ```

3. If frame enhancement shows False:
   - Check cv2 installation: `python -c "import cv2; print(cv2.__version__)"`
   - Test JPEG encoding manually

---

## Issue 5: Frames Generated But Frontend Shows Nothing ❌
**Signs**: Validation passes, test detection works, but frontend shows placeholder

### Step 1: Check Latest Frame API
```bash
curl -s http://127.0.0.1:8000/api/pothole/latest-frame/ -o test.jpg
file test.jpg
# Should say "JPEG image data", not empty
```

If 404 error:
```bash
# Check if frames are in runtime state
python manage.py shell
from fog_api.runtime_state import runtime_state
record = runtime_state.get_latest_pothole_frame()
print("Frame available:", record is not None)
```

### Step 2: Check MJPEG Stream
```bash
# Test stream endpoint
curl -N http://127.0.0.1:8000/api/pothole/stream/?source_id=phone_pothole_01 \
  --max-time 3 -o stream_frame.jpg

file stream_frame.jpg  # Check if real frame
```

### Step 3: Check Frontend Source ID
In `LiveMonitoringPage.tsx`:
- Verify `potholeSourceId` matches your camera (e.g., `phone_pothole_01`)
- Check browser console for errors:
  ```javascript
  // In browser console:
  console.log('Pothole source:', potholeSourceId);
  console.log('Backend URL:', apiBase);
  ```

### Step 4: Check CORS/Network
In browser DevTools > Network tab:
1. Look for requests to `/api/pothole/stream/`
2. Check status code (should be 200)
3. Check response preview (should show image data, not JSON error)

---

## Issue 6: FOG Detection Not Showing ❌
**Signs**: FOG stream shows placeholder, no fog data in status

### Same steps as Issue 5 but for fog:
```bash
curl -s http://127.0.0.1:8000/api/fog/latest-frame/ -o fog_test.jpg
curl -N http://127.0.0.1:8000/api/fog/stream/?source_id=phone_fog_01
```

Also check XGBoost model (fog uses XGBoost classifier)

---

## Real-Time Monitoring During Testing

**Terminal 1 - Watch Logs**:
```bash
cd fog-alert-platform/backend
tail -f logs/*.log | grep "\[DEBUG\]"
```

**Terminal 2 - Monitor Status**:
```bash
python scripts/diagnose_streams.py --loop 3
```

**Terminal 3 - Capture Frames**:
```bash
# Get latest pothole frame every 5 seconds
while true; do 
  curl -s http://127.0.0.1:8000/api/pothole/latest-frame/ -o frame_$(date +%s).jpg 2>/dev/null
  echo "Frame saved"
  sleep 5
done
```

Then open frames with: `feh frame_*.jpg`

---

## When Everything Passes But Still Broken

1. **Restart Django**: `python manage.py runserver 0.0.0.0:8000`
2. **Clear caches**: `python manage.py shell -c "from fog_api.runtime_state import runtime_state; runtime_state.clear()"`
3. **Clear browser cache**: `Ctrl+Shift+Delete` in browser
4. **Check browser console** for JavaScript errors
5. **Check Django terminal** for Python exceptions
6. **Verify source_id** matches exactly in frontend and API calls

---

## Contact for Support

If still stuck, provide:
1. Output of `validate_pipeline.py`
2. Last 50 lines of Django logs (with PIPELINE_DEBUG_LOGS=True)
3. Output of `diagnose_streams.py --loop 1`
4. Browser console screenshot
5. Frontend source ID being used

