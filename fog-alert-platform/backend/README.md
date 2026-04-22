# Fog Alert Platform Backend

Django REST API for independent fog and pothole workflows with chunked frame ingestion, cache controls, and debug-friendly responses.

## What Is Implemented

1. Independent pipelines
- `POST /api/fog/predict/` -> fog only
- `POST /api/pothole/predict/` -> pothole only
- `POST /api/combined/predict/` -> both together

2. Chunked upload support
- You can upload full image as `image`
- Or upload binary parts as `chunk` with metadata:
  - `chunk_index`
  - `total_chunks`
  - `source_id`
  - `stream_id` (recommended)
  - `frame_id` (recommended)

3. Runtime monitoring
- `GET /api/sources/status/` -> last status per source_id, counts, errors, latency

4. Cache cleanup
- `POST /api/cache/clear/`
- Optional body field: `reset_models=true` to unload in-memory model handles

5. Debug and tracing
- Every processed request returns `request_id`
- Optional debug logs controlled by `PIPELINE_DEBUG_LOGS`

## Two-Phone Use Case (Your Setup)

Use two phones with Ultralytics app as two independent input sources:

- Phone A (Fog): send frames to `/api/fog/predict/`
  - `source_id=phone_fog_01`
  - `stream_id=fog_cam`

- Phone B (Pothole): send frames to `/api/pothole/predict/`
  - `source_id=phone_pothole_01`
  - `stream_id=pothole_cam`

This keeps systems independent while sharing one backend.

## Real-Time Frame Relay From IP Webcam

For live processing, do not send a video file directly. Read the IP Webcam stream on the laptop, extract frames, and post each frame to the backend.

Recommended setup:

- Phone stream URL: `http://PHONE_IP:6969/video`
- Backend URL: `http://192.168.1.41:8000`
- Fog phone posts to `/api/fog/predict/`
- Pothole phone posts to `/api/pothole/predict/`

Run the relay from this backend folder:

```powershell
python scripts/phone_stream_relay.py --stream-url http://192.168.1.67:6969/video --backend-base http://192.168.1.41:8000 --mode fog --source-id phone_fog_01 --stream-id fog_cam --fps 5
```

For the pothole phone, change `--mode pothole`, `--source-id`, and `--stream-id`.

If the network is unstable, add chunking:

```powershell
python scripts/phone_stream_relay.py --stream-url http://192.168.1.67:6969/video --backend-base http://192.168.1.41:8000 --mode fog --source-id phone_fog_01 --stream-id fog_cam --fps 3 --chunk-size 50000
```

Use chunking only if the plain image upload is too large or the Wi-Fi is flaky. For most phones, plain JPEG frame uploads are simpler and faster.

## USB-C Alternative (No Wi-Fi Streaming)

If your phones are physically connected to the laptop with USB-C, you can avoid Wi-Fi routing issues.

1. Enable Developer options and USB debugging on both phones.
2. Start IP Webcam server on both phones (for example port 6969).
3. Connect both phones by USB-C and accept the USB debugging prompt.
4. Run:

```powershell
python scripts/setup_usb_phones.py --remote-port 6969 --backend-base http://127.0.0.1:8000
```

This script will:

- detect connected ADB devices,
- assign them as `phone_a` and `phone_b`,
- create localhost forwards to each phone IP Webcam port,
- print ready relay commands,
- save mapping to `scripts/usb_phone_map.json`.

Then run the printed relay commands. Typical URLs become:

- Phone A stream: `http://127.0.0.1:16969/video`
- Phone B stream: `http://127.0.0.1:26969/video`

If assignment order is not what you want, pass serials explicitly:

```powershell
python scripts/setup_usb_phones.py --serial-a YOUR_SERIAL_A --serial-b YOUR_SERIAL_B --remote-port 6969
```

## Endpoints

### Health
- `GET /api/health/`

### Source status
- `GET /api/sources/status/`

### Clear runtime cache
- `POST /api/cache/clear/`
- Optional form/body:
  - `reset_models=true|false`

### Fog-only inference
- `POST /api/fog/predict/`

### Pothole-only inference
- `POST /api/pothole/predict/`

### Combined inference
- `POST /api/combined/predict/`

## Input Modes

### Mode A: Single payload (simplest)
Send multipart form-data:
- `image` = full frame bytes
- `source_id` (optional)

### Mode B: Chunked payload (for unstable network / bigger payloads)
Send multipart form-data for each chunk:
- `chunk` = binary chunk
- `chunk_index` = zero-based index
- `total_chunks` = total count
- `source_id` = e.g. phone_fog_01
- `stream_id` = e.g. fog_cam
- `frame_id` = unique frame key

Behavior:
- Server returns `202 Accepted` until all chunks arrive.
- When final chunk arrives, it assembles payload and runs inference.

## Chunking Protocol Example

If one frame is split into 3 parts:

1. Send chunk 0 (`chunk_index=0`, `total_chunks=3`) -> receive 202
2. Send chunk 1 (`chunk_index=1`, `total_chunks=3`) -> receive 202
3. Send chunk 2 (`chunk_index=2`, `total_chunks=3`) -> receive 200 + inference output

All three must have same:
- `source_id`
- `stream_id`
- `frame_id`

## Request Examples

### Fog-only full image (PowerShell)

```powershell
$imagePath = "E:/6th SEM Data/Projects/AEGIS-RS_IDP/RTTS/JPEGImages/AM_Bing_211.png"
curl -X POST http://127.0.0.1:8000/api/fog/predict/ \
  -F "image=@$imagePath" \
  -F "source_id=phone_fog_01" \
  -F "stream_id=fog_cam"
```

### Pothole-only full image (PowerShell)

```powershell
$imagePath = "E:/6th SEM Data/Projects/AEGIS-RS_IDP/RTTS/JPEGImages/AM_Bing_211.png"
curl -X POST http://127.0.0.1:8000/api/pothole/predict/ \
  -F "image=@$imagePath" \
  -F "source_id=phone_pothole_01" \
  -F "stream_id=pothole_cam"
```

### Clear runtime state (and unload models)

```powershell
curl -X POST http://127.0.0.1:8000/api/cache/clear/ -F "reset_models=true"
```

### Check source runtime status

```powershell
curl http://127.0.0.1:8000/api/sources/status/
```

## Typical Response Fields

- `request_id` -> trace each request in logs
- `source_id` -> which phone/source sent frame
- `mode` -> fog_only / pothole_only / combined
- `latency_ms` -> per-request processing latency

For pothole responses:
- `detections.model_path` -> exact selected YOLO model
- `detections.task` -> detect or segment
- `detections.items[*].mask_polygon_xy` -> present when segmentation masks exist

## Environment Variables

Use `.env.example` and set these values:

Core model vars:
- `XGBOOST_FOG_DIR`
- `XGBOOST_FOG_MODEL_PATH`
- `DEHAZE_ENABLED`
- `DEHAZE_MODEL_PATH`
- `DEHAZE_IMAGE_SIZE`
- `YOLOV8_MODEL_PATH`
- `YOLOV8_AUTO_SELECT_LATEST`
- `YOLOV8_MODEL_CANDIDATES`
- `YOLOV8_CONF_THRESHOLD`
- `YOLOV8_IOU_THRESHOLD`
- `YOLOV8_MAX_DET`

Chunk/cache/debug vars:
- `STREAM_MAX_CHUNK_BYTES`
- `STREAM_MAX_CHUNKS_PER_FRAME`
- `STREAM_CHUNK_TTL_SECONDS`
- `SOURCE_STATUS_TTL_SECONDS`
- `PIPELINE_DEBUG_LOGS`

## Run Steps

```powershell
cd "E:/6th SEM Data/Projects/AEGIS-RS_IDP/fog-alert-platform/backend"
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Debugging Tips

1. Use `request_id` from API response while inspecting terminal logs.
2. Use `/api/sources/status/` to confirm each phone is sending frames.
3. If stale/incomplete chunks accumulate, call `/api/cache/clear/`.
4. If you switched model files and want a clean reload, call `/api/cache/clear/` with `reset_models=true`.

## Security Note

Do not store credentials in `.env.example` or committed files.
Create superusers locally with `python manage.py createsuperuser`.
