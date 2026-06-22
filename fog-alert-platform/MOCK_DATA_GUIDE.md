# Mock Data Configuration Guide

## Overview
Mock data generation allows you to test the dashboard UI without real camera streams or detection models. This is useful for:
- Dashboard development and testing
- Demonstrating the system while models are being debugged
- Testing frontend features without waiting for real detections
- CI/CD testing without actual hardware

## Quick Start

### Enable Mock Data
Add to your `.env` file:
```env
ENABLE_MOCK_DATA=true
MOCK_DATA_INTERVAL=2.0
MOCK_POTHOLE_PROBABILITY=0.6
MOCK_FOG_PROBABILITY=0.4
```

Then restart Django:
```bash
python manage.py runserver 0.0.0.0:8000
```

### Test It
Open your browser to the frontend and you should see:
- **Pothole Stream**: Animated frame with random pothole boxes
- **Fog Stream**: Animated frame with fog level indicators
- **Status Updates**: Mock detections every 2 seconds

## Configuration Options

### `ENABLE_MOCK_DATA` (boolean)
Enable/disable mock data generation.
```env
ENABLE_MOCK_DATA=true   # Enable
ENABLE_MOCK_DATA=false  # Disable (default)
```

### `MOCK_DATA_INTERVAL` (seconds)
How often to generate new mock frames.
```env
MOCK_DATA_INTERVAL=1.0   # Generate every 1 second (faster)
MOCK_DATA_INTERVAL=2.0   # Generate every 2 seconds (default)
MOCK_DATA_INTERVAL=5.0   # Generate every 5 seconds (slower)
```

### `MOCK_POTHOLE_PROBABILITY` (0.0 - 1.0)
Probability that a frame will contain potholes.
```env
MOCK_POTHOLE_PROBABILITY=0.6   # 60% chance of potholes (default)
MOCK_POTHOLE_PROBABILITY=0.3   # 30% chance (sparser detections)
MOCK_POTHOLE_PROBABILITY=0.9   # 90% chance (very dense detections)
```

### `MOCK_FOG_PROBABILITY` (0.0 - 1.0)
Probability that a frame will be classified as foggy.
```env
MOCK_FOG_PROBABILITY=0.4   # 40% chance of fog (default)
MOCK_FOG_PROBABILITY=0.2   # 20% chance (less foggy)
MOCK_FOG_PROBABILITY=0.8   # 80% chance (very foggy)
```

## What Mock Data Includes

### Pothole Detections
- ✓ Random bounding box coordinates
- ✓ Realistic confidence scores (0.7 - 0.99)
- ✓ Size estimates in meters
- ✓ Distance calculations (5-30m away)
- ✓ Risk scores with severity levels (CRITICAL, HIGH, MEDIUM, LOW)
- ✓ Annotated frames with colored boxes
- ✓ GPS coordinates (when enabled)
- ✓ Frame timestamps

### Fog Detections
- ✓ Fog probability values (0.0 - 1.0)
- ✓ Fog levels (HIGH, MEDIUM, LOW)
- ✓ Visibility estimates (10-200m)
- ✓ Risk scores
- ✓ Contrast measurements
- ✓ Annotated frames with fog overlay
- ✓ Frame timestamps

## How It Works

1. **Status Endpoints** (`/api/pothole/status/`, `/api/fog/status/`):
   - If no real data exists and `ENABLE_MOCK_DATA=true`
   - Returns mock data every `MOCK_DATA_INTERVAL` seconds

2. **Frame Endpoints** (`/api/pothole/latest-frame/`, `/api/fog/latest-frame/`):
   - If no real frame cached and `ENABLE_MOCK_DATA=true`
   - Returns mock annotated frame

3. **MJPEG Streams** (`/api/pothole/stream/`, `/api/fog/stream/`):
   - Falls back to mock data when available
   - Shows mock annotations in real-time

## Testing Scenarios

### Test 1: Dashboard with Mock Data Only
```bash
# 1. Disable real model loading
export ENABLE_MOCK_DATA=true
export DEHAZE_ENABLED=false
export YOLOV8_MODEL_PATH=/dev/null  # Non-existent path

# 2. Start backend
python manage.py runserver

# 3. View dashboard in browser
# You should see animated mock data without errors
```

### Test 2: Mix Real and Mock Data
```bash
# Models load but cameras aren't connected
export ENABLE_MOCK_DATA=true
export MOCK_DATA_INTERVAL=5.0  # Generate less frequently

# Start backend with real models
python manage.py runserver

# When cameras send data: real frames shown
# When cameras idle: mock data fills gaps
```

### Test 3: High-Volume Testing
```bash
# Stress test the dashboard
export ENABLE_MOCK_DATA=true
export MOCK_DATA_INTERVAL=0.5   # Every 500ms
export MOCK_POTHOLE_PROBABILITY=0.95  # Lots of potholes
export MOCK_FOG_PROBABILITY=0.8  # Foggy most of the time

# Dashboard should handle continuous data stream
```

## Integration with Real Data

When both real and mock data are enabled:

1. **Real data takes priority**
   - If actual detections exist, they're shown
   - Mock data only fills gaps when real data is absent

2. **Seamless fallback**
   - When camera goes offline → mock data starts
   - When camera comes back online → real data resumes
   - Dashboard shows no interruption

3. **Frontend doesn't know the difference**
   - Frontend code doesn't need modification
   - Both real and mock data use identical JSON format

## Detecting Mock Data (for debugging)

Responses include a `_is_mock: true` field:

```bash
curl -s http://127.0.0.1:8000/api/pothole/status/ | jq '.items[0]._is_mock'
# true if mock, undefined if real
```

## Performance Impact

Mock data generation is lightweight:
- **CPU**: < 1% per frame
- **Memory**: ~2MB for frame buffers
- **Latency**: ~10-50ms per frame

Safe to run on development machines.

## Troubleshooting

### Mock data not appearing
1. Check `ENABLE_MOCK_DATA=true` in `.env`
2. Restart Django server
3. Check logs for `[DEBUG] Mock data generator`
4. Verify `MOCK_DATA_INTERVAL` is reasonable (> 0.1 seconds)

### Mock data always shown even with real cameras
1. Check `ENABLE_MOCK_DATA=false` to disable fallback
2. Verify cameras are actually sending frames
3. Check camera source_id matches frontend setting

### Performance issues with mock data
1. Increase `MOCK_DATA_INTERVAL` (slower generation)
2. Reduce `MOCK_POTHOLE_PROBABILITY` (fewer boxes)
3. Check `REALTIME_MAX_FRAME_SIDE` isn't too large

## Environment Example

Complete `.env` for mock data testing:

```env
# Django
DEBUG=true
PIPELINE_DEBUG_LOGS=true

# Mock Data
ENABLE_MOCK_DATA=true
MOCK_DATA_INTERVAL=2.0
MOCK_POTHOLE_PROBABILITY=0.6
MOCK_FOG_PROBABILITY=0.4

# Models (can be disabled for mock-only mode)
DEHAZE_ENABLED=false
YOLOV8_MODEL_PATH=/dev/null

# Frontend
FRONTEND_POTHOLE_SOURCE_ID=phone_pothole_01
FRONTEND_FOG_SOURCE_ID=phone_fog_01
FRONTEND_STREAM_FPS=3
```

## Related Commands

```bash
# Test pothole status with mock data
curl http://127.0.0.1:8000/api/pothole/status/ | jq .

# Get latest mock pothole frame
curl http://127.0.0.1:8000/api/pothole/latest-frame/ -o mock_pothole.jpg

# Get latest mock fog frame
curl http://127.0.0.1:8000/api/fog/latest-frame/ -o mock_fog.jpg

# Stream mock MJPEG
curl -N http://127.0.0.1:8000/api/pothole/stream/ | ffplay -
```

