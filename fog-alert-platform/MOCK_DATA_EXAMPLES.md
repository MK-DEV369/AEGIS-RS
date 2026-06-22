# Mock Data - Quick Integration Examples

## Scenario 1: Dashboard Demo (No Real Models)

Use this when you want to showcase the dashboard without running models.

### Setup
```bash
# .env
ENABLE_MOCK_DATA=true
DEHAZE_ENABLED=false
YOLOV8_MODEL_PATH=/dev/null
XGBOOST_FOG_MODEL_PATH=/dev/null

# No model files needed!
```

### Test
```bash
python manage.py runserver
# Open http://localhost:5173
# See animated mock detections
```

### Result
✓ Full dashboard functionality
✓ No GPU/CUDA required
✓ Instant startup

---

## Scenario 2: Development with Real Models + Mock Fallback

Use when developing with real models but cameras aren't always connected.

### Setup
```bash
# .env
ENABLE_MOCK_DATA=true
MOCK_DATA_INTERVAL=3.0
DEHAZE_ENABLED=true
YOLOV8_MODEL_PATH=models/yolov8n.pt  # Real model
```

### Behavior
- When cameras online: Real data shown
- When cameras offline: Mock data shown automatically
- No code changes needed in frontend

### Test
```bash
# Terminal 1: Watch status
python scripts/diagnose_streams.py --loop 2

# Terminal 2: Disable cameras
# Mock data should appear within 3 seconds

# Terminal 3: Enable cameras again
# Real data should appear immediately
```

---

## Scenario 3: Performance Testing

Load test the dashboard with continuous detections.

### Setup
```bash
# .env - High frequency mock data
ENABLE_MOCK_DATA=true
MOCK_DATA_INTERVAL=0.5      # Every 500ms
MOCK_POTHOLE_PROBABILITY=0.95  # Dense detections
MOCK_FOG_PROBABILITY=0.8    # Frequent fog
```

### Test
```bash
# 1. Start backend
python manage.py runserver

# 2. Monitor in browser
# Dashboard should handle continuous updates

# 3. Check performance
curl -s http://127.0.0.1:8000/api/pothole/status/ | jq '.items[0] | {latency_ms, pothole_count}'
```

---

## Scenario 4: Testing Different Conditions

Test how dashboard responds to various edge cases.

### Sparse Detections
```bash
export MOCK_POTHOLE_PROBABILITY=0.1   # Only 10% of frames
export MOCK_FOG_PROBABILITY=0.05      # Rare fog
export MOCK_DATA_INTERVAL=5.0         # Generate slowly
```

### Dense Detections
```bash
export MOCK_POTHOLE_PROBABILITY=0.95  # Many potholes
export MOCK_FOG_PROBABILITY=0.9       # Heavy fog
export MOCK_DATA_INTERVAL=1.0         # Generate frequently
```

### Real-time Alternating
```bash
export MOCK_POTHOLE_PROBABILITY=0.5   # 50/50 chance
export MOCK_FOG_PROBABILITY=0.5
export MOCK_DATA_INTERVAL=1.0
```

---

## Scenario 5: API Testing

Test API endpoints with consistent mock data.

### Pothole API
```bash
# Check pothole status
curl -s http://127.0.0.1:8000/api/pothole/status/?source_id=phone_pothole_01 | jq '.items[0]'

# Get latest frame
curl -s http://127.0.0.1:8000/api/pothole/latest-frame/ -o frame.jpg

# Test different source IDs
for i in {1..5}; do
  curl -s "http://127.0.0.1:8000/api/pothole/status/?source_id=camera_$i" | jq '.count'
done
```

### Fog API
```bash
# Check fog status
curl -s http://127.0.0.1:8000/api/fog/status/ | jq '.items[0] | {fog_level, visibility_meters}'

# Stream fog MJPEG
curl -N http://127.0.0.1:8000/api/fog/stream/ --max-time 5
```

### Health Check
```bash
# Verify mock data is active
curl -s http://127.0.0.1:8000/api/health/ | jq '.validation.yolo.status'
```

---

## Scenario 6: Continuous Integration

Use mock data in CI/CD without real hardware.

### Docker Setup
```dockerfile
FROM python:3.11

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

ENV ENABLE_MOCK_DATA=true
ENV DISABLE_MIGRATIONS=true
ENV DEBUG=false

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

### CI Test
```bash
#!/bin/bash
# Start backend
docker run -d -p 8000:8000 fog-alert-backend

# Wait for startup
sleep 5

# Test API
for endpoint in /api/health/ /api/pothole/status/ /api/fog/status/; do
  curl -f http://localhost:8000$endpoint || exit 1
done

# Get frames
curl -f http://localhost:8000/api/pothole/latest-frame/ -o /dev/null
curl -f http://localhost:8000/api/fog/latest-frame/ -o /dev/null

echo "✓ All tests passed"
```

---

## Scenario 7: Progressive Testing

Start with mock data, gradually enable real components.

### Stage 1: Mock Only
```bash
ENABLE_MOCK_DATA=true
DEHAZE_ENABLED=false
YOLOV8_MODEL_PATH=/dev/null
# Test: Dashboard UI works with mock data
```

### Stage 2: Add Dehazer
```bash
ENABLE_MOCK_DATA=true
DEHAZE_ENABLED=true
YOLOV8_MODEL_PATH=/dev/null
# Test: Dehazer loads, mock data still used for pothole
```

### Stage 3: Add YOLO
```bash
ENABLE_MOCK_DATA=true
DEHAZE_ENABLED=true
YOLOV8_MODEL_PATH=models/yolov8n.pt
# Test: Real pothole detection, fog still mock
```

### Stage 4: Add Fog Model
```bash
ENABLE_MOCK_DATA=true
DEHAZE_ENABLED=true
YOLOV8_MODEL_PATH=models/yolov8n.pt
XGBOOST_FOG_MODEL_PATH=models/fog.joblib
# Test: Both detections real, mock as fallback
```

### Stage 5: Full System
```bash
ENABLE_MOCK_DATA=false
# All real, no mock fallback
```

---

## Command Cheatsheet

```bash
# Enable mock data quickly
echo "ENABLE_MOCK_DATA=true" >> .env

# Test with different probabilities
MOCK_POTHOLE_PROBABILITY=0.9 python manage.py runserver

# Check if mock data is active
curl -s http://127.0.0.1:8000/api/pothole/status/ | grep _is_mock

# Get mock frame in JPEG
curl http://127.0.0.1:8000/api/pothole/latest-frame/ > test.jpg && file test.jpg

# Stream mock data to file
timeout 5 curl -N http://127.0.0.1:8000/api/pothole/stream/ > stream.mjpeg

# Count mock detections
curl -s http://127.0.0.1:8000/api/pothole/status/ | jq '.items[0].pothole_count'

# Test all endpoints
for ep in health pothole/status pothole/latest-frame fog/status fog/latest-frame; do
  echo "Testing /api/$ep"
  curl -s http://127.0.0.1:8000/api/$ep/ | head -c 100
  echo
done
```

---

## Common Issues

### Mock data not showing
```bash
# Check .env was read
python manage.py shell -c "from django.conf import settings; print('ENABLE_MOCK_DATA:', settings.ENABLE_MOCK_DATA)"

# Check endpoint responds
curl -v http://127.0.0.1:8000/api/pothole/latest-frame/
```

### Real data suddenly shows as mock
```bash
# Check source_id
curl http://127.0.0.1:8000/api/pothole/status/ | jq '.items[0] | {source_id, _is_mock}'

# If source_id doesn't match, check frontend config
curl http://127.0.0.1:8000/api/frontend/config/ | jq '.default_sources'
```

### Performance slow with mock data
```bash
# Reduce generation frequency
export MOCK_DATA_INTERVAL=5.0

# Reduce detection density
export MOCK_POTHOLE_PROBABILITY=0.2
```

